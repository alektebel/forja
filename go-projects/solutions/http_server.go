package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"sync/atomic"
	"syscall"
	"time"
)

type Middleware func(http.Handler) http.Handler

type Router struct {
	routes map[string]http.Handler
}

type HealthResponse struct {
	Status    string    `json:"status"`
	Time      time.Time `json:"time"`
	RequestID string    `json:"request_id,omitempty"`
}

type GreetingResponse struct {
	Message   string `json:"message"`
	RequestID string `json:"request_id,omitempty"`
}

type EchoResponse struct {
	Received  map[string]interface{} `json:"received"`
	RequestID string                 `json:"request_id,omitempty"`
}

type ErrorResponse struct {
	Error string `json:"error"`
}

type requestIDKey struct{}

type statusWriter struct {
	http.ResponseWriter
	status int
}

func (sw *statusWriter) WriteHeader(status int) {
	sw.status = status
	sw.ResponseWriter.WriteHeader(status)
}

func NewRouter() *Router {
	return &Router{routes: make(map[string]http.Handler)}
}

func routeKey(method, path string) string {
	return method + " " + path
}

func (rt *Router) Handle(method, path string, handler http.Handler) {
	rt.routes[routeKey(method, path)] = handler
}

func (rt *Router) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	handler, ok := rt.routes[routeKey(r.Method, r.URL.Path)]
	if !ok {
		writeError(w, http.StatusNotFound, "route not found")
		return
	}
	handler.ServeHTTP(w, r)
}

func writeJSON(w http.ResponseWriter, status int, value interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(value); err != nil {
		http.Error(w, `{"error":"failed to encode response"}`, http.StatusInternalServerError)
	}
}

func writeError(w http.ResponseWriter, status int, message string) {
	writeJSON(w, status, ErrorResponse{Error: message})
}

func Chain(handler http.Handler, middlewares ...Middleware) http.Handler {
	wrapped := handler
	for i := len(middlewares) - 1; i >= 0; i-- {
		wrapped = middlewares[i](wrapped)
	}
	return wrapped
}

func requestIDFromContext(ctx context.Context) string {
	requestID, _ := ctx.Value(requestIDKey{}).(string)
	return requestID
}

func requestIDMiddleware(counter *uint64) Middleware {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			id := atomic.AddUint64(counter, 1)
			requestID := fmt.Sprintf("req-%06d", id)
			ctx := context.WithValue(r.Context(), requestIDKey{}, requestID)
			w.Header().Set("X-Request-ID", requestID)
			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

func loggingMiddleware(logger *log.Logger) Middleware {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			start := time.Now()
			sw := &statusWriter{ResponseWriter: w, status: http.StatusOK}
			next.ServeHTTP(sw, r)
			logger.Printf("method=%s path=%s status=%d request_id=%s duration=%s",
				r.Method,
				r.URL.Path,
				sw.status,
				requestIDFromContext(r.Context()),
				time.Since(start),
			)
		})
	}
}

func recoveryMiddleware(logger *log.Logger) Middleware {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			defer func() {
				if recovered := recover(); recovered != nil {
					logger.Printf("panic recovered: %v", recovered)
					writeError(w, http.StatusInternalServerError, "internal server error")
				}
			}()
			next.ServeHTTP(w, r)
		})
	}
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, HealthResponse{
		Status:    "ok",
		Time:      time.Now().UTC(),
		RequestID: requestIDFromContext(r.Context()),
	})
}

func helloHandler(w http.ResponseWriter, r *http.Request) {
	name := strings.TrimSpace(r.URL.Query().Get("name"))
	if name == "" {
		name = "world"
	}
	writeJSON(w, http.StatusOK, GreetingResponse{
		Message:   fmt.Sprintf("hello, %s", name),
		RequestID: requestIDFromContext(r.Context()),
	})
}

func echoHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "use POST for /echo")
		return
	}
	defer r.Body.Close()

	var payload map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		writeError(w, http.StatusBadRequest, "invalid JSON body")
		return
	}

	writeJSON(w, http.StatusOK, EchoResponse{
		Received:  payload,
		RequestID: requestIDFromContext(r.Context()),
	})
}

func main() {
	logger := log.New(os.Stdout, "[http-server] ", log.LstdFlags)
	router := NewRouter()
	router.Handle(http.MethodGet, "/health", http.HandlerFunc(healthHandler))
	router.Handle(http.MethodGet, "/hello", http.HandlerFunc(helloHandler))
	router.Handle(http.MethodPost, "/echo", http.HandlerFunc(echoHandler))

	var requestCounter uint64
	handler := Chain(
		router,
		requestIDMiddleware(&requestCounter),
		loggingMiddleware(logger),
		recoveryMiddleware(logger),
	)

	server := &http.Server{
		Addr:              ":8080",
		Handler:           handler,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      10 * time.Second,
		IdleTimeout:       30 * time.Second,
	}

	shutdownCtx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	go func() {
		logger.Printf("server listening on http://localhost%s", server.Addr)
		logger.Printf("try: curl http://localhost%s/health", server.Addr)
		logger.Printf("try: curl 'http://localhost%s/hello?name=Go'", server.Addr)
		logger.Printf("try: curl -X POST http://localhost%s/echo -H 'Content-Type: application/json' -d '{\"language\":\"go\"}'", server.Addr)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Fatalf("server failed: %v", err)
		}
	}()

	<-shutdownCtx.Done()
	logger.Println("shutdown signal received")

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := server.Shutdown(ctx); err != nil {
		logger.Fatalf("graceful shutdown failed: %v", err)
	}
	logger.Println("server stopped cleanly")
}
