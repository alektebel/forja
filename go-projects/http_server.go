// HTTP Server in Go - Template
// Build a tiny JSON API with routing and middleware using only the standard library.
//
// LEARNING OBJECTIVES:
// 1. Learn how `net/http` models servers, handlers, requests, and responses
// 2. Build a tiny router instead of relying on a third-party framework
// 3. Compose middleware using function types and closures
// 4. Marshal and unmarshal JSON cleanly with `encoding/json`
// 5. Practice graceful shutdown and dependency wiring in `main`
//
// ESTIMATED TIME: 4-6 hours for beginners, 2-3 hours for intermediate learners

package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"sync/atomic"
	"syscall"
	"time"
)

var (
	_ = context.Background
	_ = json.Marshal
	_ = fmt.Sprintf
	_ = log.Printf
	_ = http.MethodGet
	_ = os.Args
	_ = signal.NotifyContext
	_ = atomic.AddUint64
	_ = syscall.SIGINT
	_ = time.Second
)

/*
TODO 1: Design your routing layer and response models

CONCEPT:
Go's `net/http` package is intentionally small. That means you can build a useful mini-router
with only a few pieces:
- a map that connects a method/path pair to a handler
- a type that implements `ServeHTTP`
- a helper for registering routes

This teaches an important lesson: you do not always need a framework. Often, the standard
library already gives you enough building blocks.

GUIDELINES:
1. Create a `Middleware` function type that wraps an `http.Handler`.
2. Create a `Router` struct that stores route registrations.
3. Decide how you want to key the route map:
  - method + path combined into one string, or
  - a dedicated struct key with fields for method and path.

4. Add helper methods like:
  - `Handle(method, path string, handler http.Handler)`
  - `ServeHTTP(w http.ResponseWriter, r *http.Request)`

5. Define any response structs you want to encode as JSON.

STRUCTURE TO IMPLEMENT:
- `Middleware` type
- `Router` type with an internal route map
- one or more response structs for health checks, greetings, or errors

HINTS:
- `http.HandlerFunc` lets ordinary functions satisfy `http.Handler`.
- Think about what should happen when a route is not registered.
*/
type Middleware func(http.Handler) http.Handler

type Router struct {
	routes map[string]http.Handler
}

type HealthResponse struct {
	Status string    `json:"status"`
	Time   time.Time `json:"time"`
}

type ErrorResponse struct {
	Error string `json:"error"`
}

func NewRouter() *Router {
	panic("TODO: implement NewRouter")
}

func (rt *Router) Handle(method, path string, handler http.Handler) {
	panic("TODO: implement Router.Handle")
}

func (rt *Router) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	panic("TODO: implement Router.ServeHTTP")
}

/*
TODO 2: Write reusable JSON helpers

CONCEPT:
HTTP handlers become much cleaner when repetitive response-writing logic is centralized.
Instead of manually setting headers and writing JSON in every handler, create helpers that do it
for you in one place.

GUIDELINES:
1. Create a helper that writes JSON with a status code.
2. Set the `Content-Type` header to `application/json`.
3. Encode the response value using `json.NewEncoder` or `json.Marshal`.
4. Think about what to do if encoding fails after headers have started to go out.
5. Create a small error helper if you want consistent error responses.

STRUCTURE TO IMPLEMENT:
- `writeJSON(...)`
- optional `writeError(...)`

HINTS:
- `json.NewEncoder(w).Encode(value)` is convenient for streaming JSON to the client.
- Keep helpers generic so every handler can reuse them.
*/
func writeJSON(w http.ResponseWriter, status int, value interface{}) {
	panic("TODO: implement writeJSON")
}

func writeError(w http.ResponseWriter, status int, message string) {
	panic("TODO: implement writeError")
}

/*
TODO 3: Implement middleware chaining

CONCEPT:
Middleware in Go is just handler transformation. Each middleware takes a handler, returns a new
handler, and can do work before and/or after calling the next handler.

This project is a good chance to practice closures because your middleware will often capture
shared dependencies such as loggers or counters.

GUIDELINES:
1. Create a `Chain` function that applies middleware in order.
2. Add at least two middleware examples, such as:
  - request ID assignment
  - request logging
  - panic recovery

3. Use closures to capture state like a logger or atomic counter.
4. Decide how request IDs should flow through the program:
  - header only
  - context only
  - both header and context

STRUCTURE TO IMPLEMENT:
- `Chain(handler, middlewares...)`
- `requestIDMiddleware(...)`
- `loggingMiddleware(...)`
- `recoveryMiddleware(...)`
- optional helper to read the request ID from context

HINTS:
- A private context key type avoids collisions.
- Logging is easier if you wrap the `ResponseWriter` to track status codes.
- Recovery middleware should guard the whole handler stack.
*/
func Chain(handler http.Handler, middlewares ...Middleware) http.Handler {
	panic("TODO: implement Chain")
}

func requestIDMiddleware(counter *uint64) Middleware {
	panic("TODO: implement requestIDMiddleware")
}

func loggingMiddleware(logger *log.Logger) Middleware {
	panic("TODO: implement loggingMiddleware")
}

func recoveryMiddleware(logger *log.Logger) Middleware {
	panic("TODO: implement recoveryMiddleware")
}

/*
TODO 4: Implement handlers for a small JSON API

CONCEPT:
Handlers are just functions that turn requests into responses. Each handler should do one small
job well. Keep business logic simple and delegate repeated concerns (like JSON formatting and
logging) to helpers or middleware.

GUIDELINES:
1. Add a health endpoint that returns status information as JSON.
2. Add a hello endpoint that reads query parameters.
3. Add an echo endpoint that accepts JSON in the request body and sends JSON back.
4. Validate HTTP methods where appropriate.
5. Return useful status codes, not just `200 OK` for everything.

STRUCTURE TO IMPLEMENT:
- `healthHandler`
- `helloHandler`
- `echoHandler`
- any request/response structs needed for JSON decoding

EXAMPLES TO THINK ABOUT:
- `GET /health` should return service metadata
- `GET /hello?name=Go` should return a friendly greeting
- `POST /echo` with JSON should decode and respond with JSON
*/
func healthHandler(w http.ResponseWriter, r *http.Request) {
	panic("TODO: implement healthHandler")
}

func helloHandler(w http.ResponseWriter, r *http.Request) {
	panic("TODO: implement helloHandler")
}

func echoHandler(w http.ResponseWriter, r *http.Request) {
	panic("TODO: implement echoHandler")
}

/*
TODO 5: Wire everything together in main

CONCEPT:
`main` is where your program's dependencies are assembled. This is where you create the router,
register routes, wrap the handler chain, and start the server.

GUIDELINES:
1. Create a logger and router.
2. Register your routes.
3. Wrap the router with middleware using your chain function.
4. Create an `http.Server` with sensible timeouts.
5. Listen for OS signals and perform graceful shutdown.
6. Print useful startup information so a learner knows how to test the server.

STRUCTURE TO IMPLEMENT:
- build router
- register handlers
- wrap with middleware
- start server
- graceful shutdown on Ctrl+C / SIGTERM

HINTS:
- `signal.NotifyContext` is a clean standard-library approach.
- `server.Shutdown(ctx)` lets in-flight requests finish cleanly.
*/
func main() {
	panic("TODO: implement HTTP server main")
}
