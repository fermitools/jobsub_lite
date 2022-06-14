// utilities for working with environment variables
package env

import (
	"os"
	"strings"
)

// Default returns the value of the env var or defaultValue if it's not set.
func Default(key, defaultValue string) string {
	val := defaultValue
	if v, found := os.LookupEnv(key); found {
		val = v
	}
	return val
}

// Filter is a function that filters based on a string.
type Filter func(string) bool

// StringFilter returns a filter function that matches the exact string.
func StringFilter(str string) Filter {
	return func(x string) bool {
		return str == x
	}
}

// PrefixFilter returns a filter function that matches any string with the given
// prefix.
func PrefixFilter(prefix string) Filter {
	return func(x string) bool {
		return strings.HasPrefix(x, prefix)
	}
}

// Sanitized removes environment variables matching the given filters, and
// returns the remaining environment in the same format as os.Environ().
func Sanitized(filters ...Filter) []string {
	env := make([]string, 0, len(os.Environ()))
vars:
	for _, e := range os.Environ() {
		for _, f := range filters {
			if f(e) {
				continue vars
			}
		}
		env = append(env, e)
	}
	return env
}
