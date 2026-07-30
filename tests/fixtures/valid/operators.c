/* Maximal-munch coverage: every multi-character operator (R1.3). */
int ops(int a, int b) {
    int r = 0;
    r = a <= b;
    r = a >= b;
    r = a == b;
    r = a != b;
    r = a && b;
    r = a || b;
    r += a;
    r -= a;
    r *= a;
    r /= a;
    r %= a;
    r++;
    --r;
    r = a < b ? a : b;
    return r;
}
