/* R5.1 ACCEPTANCE FIXTURE.
   'factorial' appears as a call target and as a bare variable reference.
   The highlighter MUST give them different categories. A token-only or
   regex-only highlighter cannot, which is why it scores zero credit. */
int factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

int use(int factorial) {
    return factorial + 1;
}
