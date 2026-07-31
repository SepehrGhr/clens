/* Rows 12 and 13, block-local approximations (S6.3). */
int f(int flag) {
    int used;
    int never_read = 5;      /* row 13: unused variable, INFO */
    int uninitialized;
    used = 1;
    return used + uninitialized;   /* row 12: use before initialization, WARNING */
}
