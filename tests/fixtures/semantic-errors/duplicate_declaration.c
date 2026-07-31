/* Row 8. Note `int a = 1, a = 2;` is two sibling VarDecl nodes in one scope
   and must still fire. An inner-scope redeclaration must NOT fire as a
   duplicate (it is shadowing, row 11). */
int f(void) {
    int a = 1, a = 2;
    int b = 0;
    int b = 1;
    {
        int b = 2;   /* shadowing warning, NOT duplicate */
        return b;
    }
}
