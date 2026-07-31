/* Row 11, at three nesting depths. Each warning names both locations. */
int x = 1;

int f(int x) {          /* parameter shadows global - document the chosen behaviour */
    int y = 0;
    {
        int x = 2;      /* shadows the parameter */
        {
            int x = 3;  /* shadows the block-level x */
            y = x;
        }
    }
    return y;
}
