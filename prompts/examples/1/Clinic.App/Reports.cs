using Clinic.App.Appointments;

namespace Clinic.App.Reports;

public class DailyReport
{
    public string Build(AppointmentService appointments, DateOnly day)
    {
        var lines = appointments.On(day).Select(a => $"{a.Start:t} patient {a.PatientId}").ToList();
        ReportAudit.Write($"built report for {day} with {lines.Count} entries");
        return string.Join("\n", lines);
    }

    public void Save(string report, string path) => File.WriteAllText(path, report);
}

internal static class ReportAudit
{
    public static void Write(string message) =>
        File.AppendAllText("audit.log", $"{DateTime.UtcNow:O} reports {message}\n");
}
