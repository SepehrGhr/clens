/* Rows 7 and 9. Wrong arity must NOT also emit per-argument type errors. */
int add(int a, int b) { return a + b; }

int use(void) {
    int p = add(1);           /* row 9: expected 2 arguments, got 1 */
    int q = add(1, 2, 3);     /* row 9: expected 2 arguments, got 3 */
    int r = add(1, "two");    /* row 7: argument 2 type mismatch */
    int s = add(1, 2);        /* clean */
    return p + q + r + s;
}
