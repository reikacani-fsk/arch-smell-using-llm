using System.Diagnostics;
using System.Text.Json;
using Library.Core.Catalog;
using Library.Core.Loans;
using Library.Core.Members;
using Xunit;

namespace Library.Tests;

internal static class JsonAssert
{
    public static void RoundTrips<T>(T value) =>
        Assert.Equal(value, JsonSerializer.Deserialize<T>(JsonSerializer.Serialize(value)));
}

public class BookJsonTests
{
    [Fact]
    public void Book_round_trips() => JsonAssert.RoundTrips(new Book("978-0", "Dune", "Herbert"));
}

public class MemberJsonTests
{
    [Fact]
    public void Member_round_trips() => JsonAssert.RoundTrips(new Member(1, "Ada", false));
}

public class LoanJsonTests
{
    [Fact]
    public void Loan_round_trips() => JsonAssert.RoundTrips(
        new Loan(new Book("978-0", "Dune", "Herbert"), new Member(1, "Ada", false), new DateOnly(2026, 1, 22)));
}

internal static class LoadTestRunner
{
    public static TimeSpan Time(int times, Action action)
    {
        var watch = Stopwatch.StartNew();
        for (var i = 0; i < times; i++)
            action();
        return watch.Elapsed;
    }
}

public class CatalogLoadTests
{
    [Fact]
    public void Ten_thousand_lookups_take_under_a_second()
    {
        var catalog = new BookCatalog();
        catalog.Add(new Book("978-0", "Dune", "Herbert"));
        Assert.True(LoadTestRunner.Time(10_000, () => catalog.Find("978-0")) < TimeSpan.FromSeconds(1));
    }
}

public class MemberLoadTests
{
    [Fact]
    public void Ten_thousand_lookups_take_under_a_second()
    {
        var registry = new MemberRegistry();
        registry.Add(new Member(1, "Ada", false));
        Assert.True(LoadTestRunner.Time(10_000, () => registry.Find(1)) < TimeSpan.FromSeconds(1));
    }
}

internal static class TestDataPaths
{
    public static string Root => Path.Combine(AppContext.BaseDirectory, "data");
}

internal static class SampleCatalogFile
{
    public static string FullName => Path.Combine(TestDataPaths.Root, "catalog.json");
}

internal static class SampleMembersFile
{
    public static string FullName => Path.Combine(TestDataPaths.Root, "members.json");
}

public class FixtureFilesTests
{
    [Fact]
    public void Sample_files_exist()
    {
        Assert.True(File.Exists(SampleCatalogFile.FullName));
        Assert.True(File.Exists(SampleMembersFile.FullName));
    }
}
