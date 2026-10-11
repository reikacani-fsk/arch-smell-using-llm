namespace Clinic.App.Patients;

public record Patient(int Id, string Name);

public class PatientService
{
    private readonly List<Patient> _patients = new();

    public Patient Register(string name)
    {
        var patient = new Patient(_patients.Count + 1, name);
        _patients.Add(patient);
        PatientAudit.Write($"registered patient {patient.Id}");
        return patient;
    }

    public Patient? Find(int id) => _patients.FirstOrDefault(p => p.Id == id);
}

internal static class PatientAudit
{
    public static void Write(string message) =>
        File.AppendAllText("audit.log", $"{DateTime.UtcNow:O} patients {message}\n");
}
