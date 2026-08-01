/* All five A6 categories in one file, adapted from course document 6.5.
   1 DEAD FUNCTION      helper, never called
   2 UNREACHABLE BLOCK  after the return in foo
   3 POST-JUMP STMT     the same statement, reported structurally
   4 UNUSED VARIABLE    z, declared and never read
   5 DEAD ASSIGNMENT    y's first value, overwritten before any read */
int compute(void);
int use(int v);

void helper(void) { }

int foo(void) {
    return 42;
    int x = 0;
    return x;
}

int bar(void) {
    int y = compute();
    y = 99;
    int z = 1;
    return use(y);
}

int main(void) {
    return foo() + bar();
}
