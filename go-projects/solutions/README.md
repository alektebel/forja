# Solutions

This directory contains complete, working implementations of all Go projects.

**⚠️ IMPORTANT**: Try to implement the projects yourself first! These solutions are here for:
- **Reference** when you're stuck
- **Verification** of your approach
- **Learning** alternative implementations
- **Comparison** with your own solution

## Files

### 1. calculator.go
A standalone RPN calculator demonstrating stacks, interfaces, methods, and explicit error handling.

### 2. http_server.go
A small JSON HTTP server showing routing, middleware chaining, closures, and graceful shutdown.

### 3. concurrent_crawler.go
A concurrent crawler / link checker using goroutines, channels, mutexes, WaitGroups, and context cancellation.

### 4. key_value_store.go
An interactive key-value store with file persistence, background autosave, and a simple CLI.

## Running Solutions

```bash
cd go-projects

go run solutions/calculator.go

go run solutions/http_server.go

go run solutions/concurrent_crawler.go -url https://example.com -depth 1

go run solutions/key_value_store.go -file data.json
```
