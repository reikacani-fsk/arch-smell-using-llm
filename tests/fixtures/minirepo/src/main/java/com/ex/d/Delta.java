package com.ex.d;

public class Delta {
    public static final int LIMIT = 3;
    public enum Mode { FAST, SLOW }
    static class Inner { void hidden() { System.out.println("x"); } }
    public Delta() { }
    public String name(int i) { return "d" + i; }
}
