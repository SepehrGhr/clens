/* Library-style file with no main: dead-function analysis must not declare
   everything dead. Chosen behaviour is documented in docs/program-analysis.md. */
int add(int a, int b) { return a + b; }
int twice(int a) { return add(a, a); }
