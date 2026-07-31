/* Scope tree exercise: global, function, block, for-init, and nesting. */
int g = 1;

int outer(int p) {
    int a = p;
    {
        int b = a;
        {
            int c = b;
            a = c;
        }
    }
    for (int i = 0, j = 9; i < j; i++) {
        a = a + i;
    }
    return a + g;
}
