/* A prototype has no body, so it gets no CFG. Must not produce an empty
   graph and must not crash. */
int declared_never_defined(int n);

int defined(int n) { return n; }
