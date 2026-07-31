/* Two-pass resolution (S2.3): both must resolve cleanly. */
int later(int n);

int earlier(int n) {
    return later(n);      /* forward call via prototype */
}

int later(int n) {
    if (n <= 0) return 0;
    return earlier(n - 1);  /* mutual recursion */
}
