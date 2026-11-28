// Backend address
const API_BASE = "http://localhost:3000";


// Store driver information
let driverPhone = "";
let vehicleRegistration = "";


// Show different sections
function showSection(sectionId) {

    const sections = [
        "homeSection",
        "registerSection",
        "loginSection",
        "dashboardSection"
    ];

    sections.forEach(function(id) {
        document.getElementById(id).classList.add("hidden");
    });

    document.getElementById(sectionId).classList.remove("hidden");
}


// Register a new driver
document.getElementById("registerForm").addEventListener("submit",
    async function(event) {

        event.preventDefault();

        const fullName = document.getElementById("fullName").value.trim();
        const phone = document.getElementById("phoneNumber").value.trim();
        const registration = document.getElementById("registrationNumber").value.trim();
        const destination = document.getElementById("destination").value.trim();
        const capacityValue = document.getElementById("capacity").value;

        const message = document.getElementById("registrationMessage");

        const data = {
            full_name: fullName,
            phone_number: phone
        };

        // Vehicle details are optional, but all three must be supplied together.
        const hasAnyVehicleDetails =
            registration || destination || capacityValue;

        if (hasAnyVehicleDetails) {

            if (!registration || !destination || !capacityValue) {
                message.textContent =
                    "Please complete all vehicle details or leave them empty.";
                message.style.color = "red";
                return;
            }

            data.registration_number = registration;
            data.destination = destination;
            data.capacity = Number(capacityValue);
        }

        try {

            const response = await fetch(`${API_BASE}/driver/requests`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (response.ok) {

                driverPhone = phone;
                vehicleRegistration = registration;

                localStorage.setItem("driverPhone", phone);
                localStorage.setItem("vehicleRegistration", registration);

                message.style.color = "green";
                message.textContent =
                    "Registration submitted successfully! Your application is pending approval.";

                document.getElementById("registerForm").reset();

            } else {

                message.style.color = "red";
                message.textContent =
                    result.detail || "Registration failed. Please try again.";

            }

        } catch (error) {

            message.style.color = "red";
            message.textContent =
                "Unable to connect to the server. Please check your connection.";

            console.error(error);

        }

    }
);


// Check driver application status
async function checkApplicationStatus() {

    const phone = document.getElementById("statusPhone").value.trim();
    const message = document.getElementById("statusMessage");

    if (!phone) {
        message.textContent = "Please enter your phone number.";
        return;
    }

    try {

        const response = await fetch(
            `${API_BASE}/driver/requests/status?phone=${encodeURIComponent(phone)}`
        );

        const result = await response.json();

        if (!response.ok) {

            message.textContent =
                result.detail || "No application found.";

            return;
        }

        if (result.request_status === "pending") {

            message.innerHTML =
                "<p style='color:orange;'>Your application is still pending approval.</p>";

        } else if (result.request_status === "approved") {

            message.innerHTML =
                "<p style='color:green;'>Congratulations! Your application has been approved.</p>";

            driverPhone = phone;
            vehicleRegistration = localStorage.getItem("vehicleRegistration") || "";

            document.getElementById("driverWelcome").textContent =
                "Welcome, Driver!";

            showSection("dashboardSection");

            loadQueueInformation();

            setTimeout(loadMap, 300);

        } else if (result.request_status === "rejected") {

            message.innerHTML =
                `<p style='color:red;'>Your application was rejected.</p>
                 <p>Reason: ${escapeHTML(result.reject_reason || "No reason provided.")}</p>`;

        }

    } catch (error) {

        message.textContent =
            "Unable to connect to the server.";

        console.error(error);

    }

}


// Load queue information
async function loadQueueInformation() {

    if (!vehicleRegistration) {
        document.getElementById("queuePosition").textContent =
            "Vehicle registration unavailable";

        return;
    }

    try {

        const response = await fetch(
            `${API_BASE}/driver/turn?registration_number=${encodeURIComponent(vehicleRegistration)}`
        );

        const result = await response.json();

        if (!response.ok) {
            throw new Error("Could not load queue information.");
        }

        document.getElementById("queuePosition").textContent =
            result.queue_position ?? "--";

        document.getElementById("vehiclesAhead").textContent =
            result.vehicles_ahead ?? "--";

        document.getElementById("loadingStatus").textContent =
            result.is_my_turn ? "It is your turn!" : "Waiting in queue";

    } catch (error) {

        console.error(error);

        document.getElementById("loadingStatus").textContent =
            "Queue information unavailable.";

    }

}


// Load map
let map;
let mapMarkers = [];

async function loadMap() {

    if (typeof L === "undefined") {
        console.error("Leaflet map library did not load.");
        return;
    }

    if (!map) {

        map = L.map("map").setView([5.6037, -0.1870], 12);

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: "&copy; OpenStreetMap contributors"
        }).addTo(map);

    }

    // Remove old markers
    mapMarkers.forEach(function(marker) {
        map.removeLayer(marker);
    });

    mapMarkers = [];

    try {

        const response = await fetch(`${API_BASE}/tracking/vehicles`);

        if (!response.ok) {
            throw new Error("Could not load vehicles.");
        }

        const vehicles = await response.json();

        vehicles.forEach(function(vehicle) {

            const latitude = vehicle.latitude;
            const longitude = vehicle.longitude;

            if (latitude == null || longitude == null) {
                return;
            }

            const marker = L.marker([latitude, longitude]).addTo(map);

            marker.bindPopup(
                `Vehicle: ${escapeHTML(vehicle.registration_number || "Unknown")}<br>
                 Destination: ${escapeHTML(vehicle.destination || "Unknown")}`
            );

            mapMarkers.push(marker);

        });

        setTimeout(function() {
            map.invalidateSize();
        }, 200);

    } catch (error) {

        console.error("Map error:", error);

    }

}


// Prevent text from being treated as HTML
function escapeHTML(value) {

    return String(value).replace(/[&<>"']/g, function(character) {

        const replacements = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        };

        return replacements[character];

    });

}


// Logout
function logout() {

    showSection("homeSection");

}


// Load saved information
window.addEventListener("DOMContentLoaded", function() {

    driverPhone = localStorage.getItem("driverPhone") || "";

    vehicleRegistration =
        localStorage.getItem("vehicleRegistration") || "";

});