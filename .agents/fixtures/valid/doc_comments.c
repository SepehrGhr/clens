/* Hover doc-comment attachment (S7). Every declaration below has a preceding
   comment that hover must find and strip. */

/* Computes n factorial recursively. */
int factorial(int n) {
    return n <= 1 ? 1 : n * factorial(n - 1);
}

// A running total.
// Spans two line comments, which hover must join.
int total = 0;

/**
 * Decorated block comment; leading asterisks must be stripped.
 */
int decorated(void) {
    return 0;
}
