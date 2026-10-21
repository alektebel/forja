// Calculator in Go - Template
// Build a Reverse Polish Notation (RPN) calculator using stacks and explicit error handling.
//
// LEARNING OBJECTIVES:
// 1. Define custom types and attach methods to them
// 2. Use interfaces to model interchangeable operator behavior
// 3. Practice stack-based problem solving with slices
// 4. Use switch statements to classify tokens and route logic
// 5. Return descriptive errors instead of relying on exceptions
//
// ESTIMATED TIME: 3-5 hours for beginners, 1-2 hours for intermediate learners

package main

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)

var (
	_ = fmt.Printf
	_ = os.Args
	_ = strconv.ParseFloat
	_ = strings.Fields
)

/*
TODO 1: Model calculator errors and the stack abstraction

CONCEPT:
Go prefers explicit error handling. Instead of throwing exceptions, functions usually return
`(value, error)`. This project is a great place to practice designing meaningful error types
rather than returning vague strings everywhere.

A stack is also the core data structure in an RPN calculator. Every number token is pushed,
and every operator pops the operands it needs. That means your stack API should be tiny,
clear, and safe.

GUIDELINES:
 1. Create a named type for different categories of calculator failures.
    Examples of categories you may want: invalid token, stack underflow, malformed expression,
    divide by zero.
 2. Create a struct that implements the `error` interface by defining an `Error() string` method.
 3. Decide what extra context is useful to include in an error:
    - the token being processed
    - the reason for failure
    - the kind/category of error
 4. Create a `Stack` type backed by a slice.
 5. Give the stack focused methods such as:
    - `Push`
    - `Pop`
    - `Len`
 6. Think carefully about how `Pop` should behave when the stack is empty.

STRUCTURE TO IMPLEMENT:
- A `CalcErrorKind` type to classify failures
- A `CalcError` struct holding useful debugging information
- A `Stack` struct that stores numeric values
- Methods on `Stack` for safe stack manipulation

HINTS:
- A slice is the natural backing store for a stack in Go.
- The last element of a slice is the top of the stack.
- If `Pop` fails, return a zero value plus a descriptive error.
- Keep the stack implementation small; it should be easy to trust.
*/
type CalcErrorKind string

type CalcError struct {
	Kind    CalcErrorKind
	Token   string
	Message string
}

type Stack struct {
	items []float64
}

func (e *CalcError) Error() string {
	panic("TODO: implement CalcError.Error")
}

func (s *Stack) Push(value float64) {
	panic("TODO: implement Stack.Push")
}

func (s *Stack) Pop() (float64, error) {
	panic("TODO: implement Stack.Pop")
}

func (s *Stack) Len() int {
	panic("TODO: implement Stack.Len")
}

/*
TODO 2: Design the operator system with interfaces and concrete implementations

CONCEPT:
An interface lets you describe behavior without committing every caller to one exact concrete
struct type. For a calculator, every operator shares the same high-level behavior:
- it has a symbol (like `+` or `/`)
- it can apply itself to two operands

This is a useful exercise because it shows how Go interfaces can model behavior in a simple,
practical way without complex inheritance hierarchies.

GUIDELINES:
1. Define an `Operator` interface that captures the behavior required by the calculator.
2. Create one or more concrete operator types that satisfy that interface.
3. Think about whether you want:
  - one struct per operator (`AddOperator`, `SubOperator`, etc.), or
  - one reusable struct configured with a symbol and function.

4. Decide where operators should live. A common pattern is a map from symbol to operator.
5. Make sure division handles the special case where the right operand is zero.

STRUCTURE TO IMPLEMENT:
- An `Operator` interface
- A concrete operator implementation
- A `Calculator` struct that stores registered operators
- A constructor that creates a calculator with built-in operators

HINTS:
  - A function field can be a clean way to avoid repetitive operator structs.
  - If division by zero occurs, return an error instead of panicking.
  - Your calculator should not need to know the internal details of each operator; it should
    only call interface methods.
*/
type Operator interface {
	Symbol() string
	Apply(left, right float64) (float64, error)
}

type Calculator struct {
	operators map[string]Operator
}

func NewCalculator() *Calculator {
	panic("TODO: implement NewCalculator")
}

/*
TODO 3: Parse and evaluate an RPN expression token by token

CONCEPT:
RPN evaluation is a pipeline:
1. Split the input into tokens
2. For each token, decide whether it is a number or operator
3. Update the stack accordingly
4. Validate that exactly one final result remains

This is where a `switch` statement becomes useful: it helps you branch on the type of token
or on parsing success in a way that stays readable.

GUIDELINES:
1. Split the expression using whitespace.
2. Handle the empty-expression case explicitly.
3. For each token:
  - if it parses as a number, push it
  - otherwise, look it up in the operator registry
  - if it is unknown, return an error immediately

4. When applying an operator, pop operands in the correct order:
  - the first pop is usually the right operand
  - the second pop is usually the left operand

5. After processing all tokens, require the stack length to be exactly 1.
6. If more than one value remains, the expression was incomplete or malformed.

STRUCTURE TO IMPLEMENT:
- A helper like `isNumber` or direct parsing inside the loop
- A method such as `Evaluate(expression string) (float64, error)`
- Final validation for malformed expressions

EXAMPLES TO THINK ABOUT:
- `"3 4 +"` should succeed
- `"10 2 / 5 +"` should succeed
- `"3 +"` should fail because there are not enough operands
- `"3 4 5 +"` should fail because too many values remain on the stack
- `"2 0 /"` should fail with a divide-by-zero error
*/
func (c *Calculator) Evaluate(expression string) (float64, error) {
	panic("TODO: implement Calculator.Evaluate")
}

func isNumber(token string) bool {
	panic("TODO: implement isNumber")
}

/*
TODO 4: Build a small CLI experience around the calculator

CONCEPT:
Even a tiny command-line entry point teaches an important Go lesson: business logic should be
separate from input/output. The calculator logic should live in methods and helpers, while
`main` should mainly gather input, call into your calculator, and print results.

GUIDELINES:
 1. Accept an expression from command-line arguments, or provide sample expressions when no
    arguments are passed.
 2. Join multiple CLI arguments into a single expression string.
 3. Print either the final numeric result or a helpful error message.
 4. Keep `main` thin; most real logic should already exist in other functions.

STRUCTURE TO IMPLEMENT:
- A helper for formatting numeric output if you want cleaner printing
- A `main` function that creates a calculator and runs one expression or many examples

HINTS:
- `strings.Join(os.Args[1:], " ")` is often useful when expressions are passed as separate args.
- It is okay for `main` to demonstrate several test inputs if no arguments are provided.
*/
func formatNumber(value float64) string {
	panic("TODO: implement formatNumber")
}

func main() {
	panic("TODO: implement calculator CLI")
}
