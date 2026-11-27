
import 'package:flutter/material.dart';
import 'login_screen.dart';

class RoleSelectionScreen extends StatelessWidget {
  const RoleSelectionScreen({super.key});

  static const Color darkGreen = Color(0xFF17554A);
  static const Color lightGreen = Color(0xFFEAF3EF);

  final List<Map<String, String>> roles = const [
    {
      'title': 'Driver',
      'description': 'Manage your vehicle and trips.',
      'role': 'driver',
      'icon': 'directions_bus',
    },
    {
      'title': 'Mate',
      'description': 'Manage passengers and departures.',
      'role': 'mate',
      'icon': 'groups',
    },
    {
      'title': 'Commuter',
      'description': 'Find routes and explore available trips.',
      'role': 'commuter',
      'icon': 'person',
    },
    {
      'title': 'Station Manager',
      'description': 'Oversee station operations.',
      'role': 'station_manager',
      'icon': 'admin_panel_settings',
    },
  ];

  IconData _getIcon(String name) {
    switch (name) {
      case 'directions_bus':
        return Icons.directions_bus;
      case 'groups':
        return Icons.groups;
      case 'person':
        return Icons.person;
      default:
        return Icons.admin_panel_settings;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF7FAF8),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 480),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(
                    Icons.directions_bus_filled,
                    color: darkGreen,
                    size: 42,
                  ),
                  const SizedBox(height: 20),
                  const Text(
                    'Welcome to trotro',
                    style: TextStyle(
                      fontSize: 30,
                      fontWeight: FontWeight.bold,
                      color: darkGreen,
                    ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Choose your role to continue.',
                    style: TextStyle(
                      fontSize: 16,
                      color: Colors.black54,
                    ),
                  ),
                  const SizedBox(height: 28),

                  ...roles.map((item) {
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 14),
                      child: InkWell(
                        borderRadius: BorderRadius.circular(18),
                        onTap: () {
                          Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (_) => LoginScreen(
                                role: item['role']!,
                                roleTitle: item['title']!,
                              ),
                            ),
                          );
                        },
                        child: Container(
                          padding: const EdgeInsets.all(20),
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(18),
                            border: Border.all(
                              color: const Color(0xFFDCE8E1),
                            ),
                          ),
                          child: Row(
                            children: [
                              Container(
                                width: 52,
                                height: 52,
                                decoration: BoxDecoration(
                                  color: lightGreen,
                                  borderRadius: BorderRadius.circular(14),
                                ),
                                child: Icon(
                                  _getIcon(item['icon']!),
                                  color: darkGreen,
                                  size: 27,
                                ),
                              ),
                              const SizedBox(width: 16),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment:
                                      CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      item['title']!,
                                      style: const TextStyle(
                                        fontSize: 17,
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                    const SizedBox(height: 5),
                                    Text(
                                      item['description']!,
                                      style: const TextStyle(
                                        color: Colors.black54,
                                        fontSize: 13,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              const Icon(
                                Icons.arrow_forward_ios,
                                size: 16,
                                color: darkGreen,
                              ),
                            ],
                          ),
                        ),
                      ),
                    );
                  }),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}