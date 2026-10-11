using Clinic.App.Patients;

namespace Clinic.App.Appointments;

public record Appointment(int PatientId, DateTime Start);

public class AppointmentService
{
    private readonly List<Appointment> _appointments = new();

    public Appointment Book(Patient patient, DateTime start)
    {
        var appointment = new Appointment(patient.Id, start);
        _appointments.Add(appointment);
        AppointmentAudit.Write($"booked patient {patient.Id} at {start:t}");
        return appointment;
    }

    public IEnumerable<Appointment> On(DateOnly day) => _appointments.Where(a => DateOnly.FromDateTime(a.Start) == day);
}

internal static class AppointmentAudit
{
    public static void Write(string message) =>
        File.AppendAllText("audit.log", $"{DateTime.UtcNow:O} appointments {message}\n");
}
