/* typedef is deliberately out of scope (decision D3).
   Expected: a clear "unsupported construct" diagnostic, then recovery,
   and the following function must still parse. */
typedef int myint;

int f(void) {
    return 1;
}
