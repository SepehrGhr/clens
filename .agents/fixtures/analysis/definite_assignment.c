/* A2.1 golden case, from course document 6.1.1.
   `x` is assigned only on the true path, so the read at the end is a
   definite-assignment violation. Phase 2's crude row-12 check did NOT catch
   this; the real analysis must. */
int report(int value);

int f(int condition) {
    int x;
    if (condition) { x = 42; }
    return report(x);        /* WARNING: x uninitialized on the false path */
}

int g(int condition) {
    int y;
    if (condition) { y = 1; } else { y = 2; }
    return report(y);        /* clean: assigned on every path */
}
