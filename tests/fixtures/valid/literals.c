/* Every literal form required by R1.2. */
#include <stdio.h>

int ints(void) {
    int dec = 42;
    int hex = 0xFF;
    int bin = 0b1010;
    int oct = 0755;
    int suf = 100UL;
    return dec + hex + bin + oct + suf;
}

double floats(void) {
    double a = 3.14;
    double b = 1.0e-5;
    float  c = .5f;
    double d = 1.;
    double e = 1e10;
    return a + b + c + d + e;
}

void text(void) {
    char *s = "hello\n";
    char *q = "say \"hi\"";
    char *empty = "";
    char c1 = 'a';
    char c2 = '\t';
    char c3 = '\0';
    char c4 = '\'';
}
