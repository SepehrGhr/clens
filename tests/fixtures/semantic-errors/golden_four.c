/* The four worked examples from course document 5.3.1 (S4.7).
   Expected, in order:
     line 6  WARNING  narrowing double -> int
     line 7  ERROR    cannot assign int to char*
     line 8  ERROR    argument type mismatch: expected int, got char*
     line 9  ERROR    void function returning a value           */
int factorial(int n);

int x = 3.14;
char *s = 42;
int y = factorial("hello");
void foo(void) { return 5; }
