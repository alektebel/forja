package main

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)

type CalcErrorKind string

const (
	ErrInvalidToken        CalcErrorKind = "invalid_token"
	ErrStackUnderflow      CalcErrorKind = "stack_underflow"
	ErrMalformedExpression CalcErrorKind = "malformed_expression"
	ErrDivideByZero        CalcErrorKind = "divide_by_zero"
)

type CalcError struct {
	Kind    CalcErrorKind
	Token   string
	Message string
}

func (e *CalcError) Error() string {
	if e == nil {
		return "<nil>"
	}
	if e.Token == "" {
		return fmt.Sprintf("%s: %s", e.Kind, e.Message)
	}
	return fmt.Sprintf("%s (%s): %s", e.Kind, e.Token, e.Message)
}

type Stack struct {
	items []float64
}

func (s *Stack) Push(value float64) {
	s.items = append(s.items, value)
}

func (s *Stack) Pop() (float64, error) {
	if len(s.items) == 0 {
		return 0, &CalcError{Kind: ErrStackUnderflow, Message: "not enough operands on the stack"}
	}

	last := len(s.items) - 1
	value := s.items[last]
	s.items = s.items[:last]
	return value, nil
}

func (s *Stack) Len() int {
	return len(s.items)
}

type Operator interface {
	Symbol() string
	Apply(left, right float64) (float64, error)
}

type BinaryOperator struct {
	symbol string
	apply  func(left, right float64) (float64, error)
}

func (op BinaryOperator) Symbol() string {
	return op.symbol
}

func (op BinaryOperator) Apply(left, right float64) (float64, error) {
	return op.apply(left, right)
}

type Calculator struct {
	operators map[string]Operator
}

func NewCalculator() *Calculator {
	calculator := &Calculator{operators: make(map[string]Operator)}

	builtins := []Operator{
		BinaryOperator{symbol: "+", apply: func(left, right float64) (float64, error) { return left + right, nil }},
		BinaryOperator{symbol: "-", apply: func(left, right float64) (float64, error) { return left - right, nil }},
		BinaryOperator{symbol: "*", apply: func(left, right float64) (float64, error) { return left * right, nil }},
		BinaryOperator{symbol: "/", apply: func(left, right float64) (float64, error) {
			if right == 0 {
				return 0, &CalcError{Kind: ErrDivideByZero, Token: "/", Message: "cannot divide by zero"}
			}
			return left / right, nil
		}},
	}

	for _, operator := range builtins {
		calculator.operators[operator.Symbol()] = operator
	}

	return calculator
}

func (c *Calculator) Evaluate(expression string) (float64, error) {
	tokens := strings.Fields(expression)
	if len(tokens) == 0 {
		return 0, &CalcError{Kind: ErrMalformedExpression, Message: "expression is empty"}
	}

	stack := &Stack{}
	for _, token := range tokens {
		switch {
		case isNumber(token):
			value, _ := strconv.ParseFloat(token, 64)
			stack.Push(value)
		default:
			operator, ok := c.operators[token]
			if !ok {
				return 0, &CalcError{Kind: ErrInvalidToken, Token: token, Message: "unknown token"}
			}

			right, err := stack.Pop()
			if err != nil {
				return 0, &CalcError{Kind: ErrMalformedExpression, Token: token, Message: "operator requires two operands"}
			}

			left, err := stack.Pop()
			if err != nil {
				return 0, &CalcError{Kind: ErrMalformedExpression, Token: token, Message: "operator requires two operands"}
			}

			result, err := operator.Apply(left, right)
			if err != nil {
				return 0, err
			}
			stack.Push(result)
		}
	}

	if stack.Len() != 1 {
		return 0, &CalcError{Kind: ErrMalformedExpression, Message: "expression did not reduce to a single result"}
	}

	return stack.Pop()
}

func isNumber(token string) bool {
	_, err := strconv.ParseFloat(token, 64)
	return err == nil
}

func formatNumber(value float64) string {
	if value == float64(int64(value)) {
		return strconv.FormatInt(int64(value), 10)
	}
	return strconv.FormatFloat(value, 'f', -1, 64)
}

func main() {
	calculator := NewCalculator()

	if len(os.Args) > 1 {
		expression := strings.Join(os.Args[1:], " ")
		result, err := calculator.Evaluate(expression)
		if err != nil {
			fmt.Printf("error: %v\n", err)
			os.Exit(1)
		}
		fmt.Println(formatNumber(result))
		return
	}

	samples := []string{
		"3 4 +",
		"10 2 / 5 +",
		"5 1 2 + 4 * + 3 -",
		"9 3 / 2 *",
		"2 0 /",
		"3 +",
	}

	fmt.Println("RPN Calculator Solution")
	fmt.Println("Pass an expression as arguments, for example:")
	fmt.Println("  go run solutions/calculator.go 3 4 +")
	fmt.Println()
	fmt.Println("Sample evaluations:")

	for _, expression := range samples {
		result, err := calculator.Evaluate(expression)
		if err != nil {
			fmt.Printf("%-22s -> error: %v\n", expression, err)
			continue
		}
		fmt.Printf("%-22s -> %s\n", expression, formatNumber(result))
	}
}
