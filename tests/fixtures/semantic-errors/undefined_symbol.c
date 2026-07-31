/* No-cascade test (S9.2): 'counter' is undefined and used five times.
   Expected: exactly ONE diagnostic. */
int use(void) {
    counter = 1;
    counter = counter + 1;
    return counter * counter;
}
