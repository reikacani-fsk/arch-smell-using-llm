using Clinic.App.Appointments;
using Clinic.App.Patients;

namespace Clinic.App.Integration;

public class MessageGateway
{
    private readonly PatientService _patients = new();
    private readonly AppointmentService _appointments = new();

    public object? Handle(string command, object payload) => command switch
    {
        "register" => _patients.Register((string)payload),
        "find" => _patients.Find((int)payload),
        "book" => _appointments.Book((Patient)((object[])payload)[0], (DateTime)((object[])payload)[1]),
        _ => throw new ArgumentException($"unknown command {command}"),
    };
}
