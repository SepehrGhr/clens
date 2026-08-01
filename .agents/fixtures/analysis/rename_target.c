/* A5.3 golden rename fixture, from course document 6.4.
   Renaming `n` at its declaration in factorial to `number` must change ONLY
   factorial's occurrences. `other` and `shadow_demo` must come back
   byte-identical — that contrast is the whole test.
   Also here for the refusal cases:
     - renaming factorial's `n` to `result` collides in the same scope
     - renaming factorial's `n` to `g` would shadow the global */
int g = 0;

int factorial(int n) {
    int result = 1;
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

int other(int n) {
    return n + n;
}

int shadow_demo(void) {
    int n = 5;
    {
        int inner = n;
        return inner;
    }
}
