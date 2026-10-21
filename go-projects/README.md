# Go Projects

This directory contains various projects to learn Go from scratch. Each project comes with verbose implementation guidelines that explain **what** to implement and **how** to approach it, without providing the actual implementation code.

## Goal
Learn Go by implementing real-world projects to understand:
- **Go Syntax and Type System**: structs, interfaces, methods, slices, maps, pointers
- **Error Handling**: explicit error returns, custom error types, defensive programming
- **Standard Library Mastery**: `net/http`, `encoding/json`, `os`, `context`, `sync`
- **Concurrency**: goroutines, channels, mutexes, WaitGroups, cancellation
- **Systems Thinking**: persistence, routing, command parsing, data flow between components

## Philosophy

These projects follow the "learn by doing" approach:
- ✅ **Verbose Guidelines**: Each TODO comment includes detailed explanations
- ✅ **No Direct Solutions**: Guidelines explain concepts without giving away the code
- ✅ **Progressive Complexity**: Start simple, add features incrementally
- ✅ **Real-World Relevance**: Projects mirror actual Go programs you would build in practice
- ✅ **Conceptual Focus**: Understand Go idioms, not just syntax

## Projects Overview

### 1. **Calculator**
**Complexity**: Beginner  
**File**: `calculator.go`  
**Focus**: structs, interfaces, switch statements, error handling, stacks

Build a Reverse Polish Notation (RPN) calculator that processes tokens using a stack and a registry of operators.

**Key Learning Points**:
- Defining custom types and attaching methods to them
- Using interfaces to model interchangeable behavior
- Implementing stack-based evaluation with slices
- Validating input and returning useful errors
- Using `switch` statements to direct parsing logic

**What You'll Build**: A calculator that evaluates expressions like `"3 4 +"`, `"10 2 / 5 +"`, and reports errors for malformed input.

### 2. **HTTP Server**
**Complexity**: Intermediate  
**File**: `http_server.go`  
**Focus**: `net/http`, handler functions, middleware chaining, JSON

Implement a simple HTTP server with a tiny router, reusable middleware, and JSON responses.

**Key Learning Points**:
- Working with Go's standard HTTP server primitives
- Treating functions as values when composing middleware
- Marshaling and unmarshaling JSON with `encoding/json`
- Structuring request handlers cleanly
- Using closures to capture shared dependencies like loggers or counters

**What You'll Build**: A small JSON API with routes such as health checks, greetings, and an echo endpoint.

### 3. **Concurrent Crawler**
**Complexity**: Intermediate-Advanced  
**File**: `concurrent_crawler.go`  
**Focus**: goroutines, channels, WaitGroups, mutexes, context cancellation

Create a concurrent link checker / crawler that visits pages, extracts links, and coordinates work across multiple workers.

**Key Learning Points**:
- Modeling work with channels and worker pools
- Protecting shared state from race conditions with mutexes
- Coordinating concurrent jobs with WaitGroups
- Cancelling ongoing work with `context.Context`
- Building fan-out / fan-in pipelines

**What You'll Build**: A CLI program that crawls a starting URL up to a configurable depth and prints a summary of visited pages.

### 4. **Key-Value Store**
**Complexity**: Advanced  
**File**: `key_value_store.go`  
**Focus**: maps, file I/O, encoding/decoding, interfaces, background sync

Build an in-memory key-value store with persistence to disk and a simple command-line interface.

**Key Learning Points**:
- Designing interfaces for storage behavior
- Using maps safely behind mutexes
- Saving and loading structured data from files
- Parsing commands from user input
- Running a background goroutine for periodic syncing

**What You'll Build**: An interactive CLI store that supports commands such as `set`, `get`, `delete`, `list`, and autosaves data to disk.

## Learning Path

### Phase 1: Foundations (Start Here)
1. **Calculator** - Learn Go syntax, methods, slices, and explicit error handling

### Phase 2: Standard Library Confidence
2. **HTTP Server** - Build intuition for handlers, JSON, and middleware composition

### Phase 3: Concurrency in Practice
3. **Concurrent Crawler** - Combine goroutines, channels, synchronization, and cancellation

### Phase 4: Stateful Programs
4. **Key-Value Store** - Bring together persistence, interfaces, concurrency, and CLI design

## Getting Started

### Prerequisites
- Go installed (Go 1.20+ recommended)
- Basic familiarity with variables, loops, and functions
- Comfort using a terminal and running `go run`

### Installation

```bash
# On macOS:
brew install go

# On Ubuntu / Debian:
sudo apt-get update
sudo apt-get install golang-go

# Verify installation:
go version
```

### Running a Project

```bash
# Navigate to the go-projects directory
cd go-projects

# Run a template after you implement it
go run calculator.go

# Run a complete solution
go run solutions/calculator.go

# Try another solution
go run solutions/http_server.go
```

## Project Structure

Each project file contains:
- **Package declaration** and imports
- **Type definitions** with TODOs and skeletons
- **Function templates** with detailed implementation hints
- **Implementation guide comments** explaining the overall approach
- **Learning points** embedded directly inside the TODO sections
- **A matching solution** in `solutions/` with a complete working implementation

## Resources

### Books
- "The Go Programming Language" by Alan A. A. Donovan and Brian W. Kernighan
- "Learning Go" by Jon Bodner
- "Network Programming with Go" by Adam Woodbeck
- "Concurrency in Go" by Katherine Cox-Buday

### Online Resources
- Go Tour: https://go.dev/tour/
- Effective Go: https://go.dev/doc/effective_go
- Go by Example: https://gobyexample.com/
- Go Documentation: https://pkg.go.dev/std
- Go Blog: https://go.dev/blog/

### Practice
- Exercism Go track
- Project Euler in Go
- Advent of Code in Go
- Build small CLI tools with the standard library only

## Video Courses & Resources

**Go Fundamentals**:
- [A Tour of Go](https://go.dev/tour/)
- [JustForFunc: Programming in Go](https://www.youtube.com/c/JustForFunc)
- [Go Time](https://changelog.com/gotime)

**Systems & Concurrency**:
- [Advanced Go Concurrency Patterns](https://go.dev/blog/io2013-talk-concurrency)
- [GopherCon Talks](https://www.youtube.com/c/GopherAcademy)
