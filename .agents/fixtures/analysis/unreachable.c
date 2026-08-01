/* A2.3, from course document 6.1.1. Both patterns must warn. */
int foo(void) {
    return 42;
    return 0;                /* UNREACHABLE: after unconditional return */
}

void bar(int x) {
    if (x > 0) {
        return;
        x++;                 /* UNREACHABLE: after return in the if-branch */
    }
}
