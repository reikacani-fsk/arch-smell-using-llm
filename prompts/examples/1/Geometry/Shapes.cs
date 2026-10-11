namespace Geometry.Shapes;

public interface IShape
{
    double Area { get; }
}

public abstract record RegularPolygon(int Sides, double Side) : IShape
{
    public double Area => Sides * Side * Side / (4 * Math.Tan(Math.PI / Sides));
}

public record Triangle(double Side) : RegularPolygon(3, Side);
public record Square(double Side) : RegularPolygon(4, Side);
public record Pentagon(double Side) : RegularPolygon(5, Side);
public record Hexagon(double Side) : RegularPolygon(6, Side);
public record Heptagon(double Side) : RegularPolygon(7, Side);
public record Octagon(double Side) : RegularPolygon(8, Side);
public record Nonagon(double Side) : RegularPolygon(9, Side);
public record Decagon(double Side) : RegularPolygon(10, Side);
public record Hendecagon(double Side) : RegularPolygon(11, Side);
public record Dodecagon(double Side) : RegularPolygon(12, Side);
public record Tridecagon(double Side) : RegularPolygon(13, Side);
public record Tetradecagon(double Side) : RegularPolygon(14, Side);
public record Pentadecagon(double Side) : RegularPolygon(15, Side);
public record Hexadecagon(double Side) : RegularPolygon(16, Side);
public record Heptadecagon(double Side) : RegularPolygon(17, Side);
public record Octadecagon(double Side) : RegularPolygon(18, Side);
public record Enneadecagon(double Side) : RegularPolygon(19, Side);
public record Icosagon(double Side) : RegularPolygon(20, Side);

public record Circle(double Radius) : IShape { public double Area => Math.PI * Radius * Radius; }
public record Semicircle(double Radius) : IShape { public double Area => Math.PI * Radius * Radius / 2; }
public record Sector(double Radius, double Angle) : IShape { public double Area => Angle / 2 * Radius * Radius; }
public record Annulus(double Outer, double Inner) : IShape { public double Area => Math.PI * (Outer * Outer - Inner * Inner); }
public record Ellipse(double A, double B) : IShape { public double Area => Math.PI * A * B; }
public record Rectangle(double Width, double Height) : IShape { public double Area => Width * Height; }
public record Parallelogram(double Base, double Height) : IShape { public double Area => Base * Height; }
public record Rhombus(double D1, double D2) : IShape { public double Area => D1 * D2 / 2; }
public record Kite(double D1, double D2) : IShape { public double Area => D1 * D2 / 2; }
public record Trapezoid(double A, double B, double Height) : IShape { public double Area => (A + B) / 2 * Height; }
public record RightTriangle(double A, double B) : IShape { public double Area => A * B / 2; }
public record IsoscelesTriangle(double Base, double Height) : IShape { public double Area => Base * Height / 2; }
