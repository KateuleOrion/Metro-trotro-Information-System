
import 'package:flutter/material.dart';
import '../services/auth_service.dart';
import 'home_screen.dart';
import 'passenger_register_screen.dart';

class LoginScreen extends StatefulWidget {
  final String role;
  final String roleTitle;

  const LoginScreen({
    super.key,
    required this.role,
    required this.roleTitle,
  });

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _phoneController = TextEditingController();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  final AuthService _authService = AuthService();

  bool _usePhone = true;
  bool _obscurePassword = true;
  bool _isLoading = false;

  static const Color darkGreen = Color(0xFF17554A);

  String _normalisePhone(String input) {
    String digits = input.replaceAll(RegExp(r'\D'), '');

    if (digits.startsWith('0')) {
      digits = '233${digits.substring(1)}';
    } else if (!digits.startsWith('233')) {
      digits = '233$digits';
    }

    return '+$digits';
  }

  Future<void> _login() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isLoading = true);

    try {
      if (widget.role == 'commuter') {
        // Passenger login
        await _authService.passengerLogin(
          phoneNumber: _normalisePhone(_phoneController.text),
          password: _passwordController.text,
        );

        if (!mounted) return;

        Navigator.pushAndRemoveUntil(
          context,
          MaterialPageRoute(
            builder: (_) => const HomeScreen(),
          ),
          (route) => false,
        );
      } else {
        // Staff login
        await _authService.login(
          password: _passwordController.text,
          role: widget.role,
          phone: _usePhone
              ? _normalisePhone(_phoneController.text)
              : null,
          email: _usePhone
              ? null
              : _emailController.text.trim(),
        );

        if (!mounted) return;

        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              '${widget.roleTitle} login successful. '
              'The ${widget.roleTitle} dashboard is not part '
              'of this passenger app.',
            ),
            duration: const Duration(seconds: 5),
          ),
        );
      }
    } catch (error) {
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            error.toString().replaceFirst('Exception: ', ''),
          ),
          backgroundColor: Colors.red.shade700,
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  @override
  void dispose() {
    _phoneController.dispose();
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isPassenger = widget.role == 'commuter';

    return Scaffold(
      backgroundColor: const Color(0xFFF7FAF8),
      appBar: AppBar(
        backgroundColor: const Color(0xFFF7FAF8),
        foregroundColor: darkGreen,
        elevation: 0,
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(
                      Icons.directions_bus_filled,
                      size: 42,
                      color: darkGreen,
                    ),
                    const SizedBox(height: 22),

                    Text(
                      'Welcome, ${widget.roleTitle}',
                      style: const TextStyle(
                        fontSize: 28,
                        fontWeight: FontWeight.bold,
                        color: darkGreen,
                      ),
                    ),
                    const SizedBox(height: 8),

                    const Text(
                      'Sign in to continue to your account.',
                      style: TextStyle(
                        color: Colors.black54,
                        fontSize: 15,
                      ),
                    ),
                    const SizedBox(height: 30),

                    if (!isPassenger) ...[
                      const Text(
                        'Sign in with',
                        style: TextStyle(
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 10),

                      Row(
                        children: [
                          Expanded(
                            child: _methodButton(
                              label: 'Phone number',
                              selected: _usePhone,
                              onTap: () {
                                setState(() => _usePhone = true);
                              },
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: _methodButton(
                              label: 'Email',
                              selected: !_usePhone,
                              onTap: () {
                                setState(() => _usePhone = false);
                              },
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 22),
                    ],

                    Text(
                      _usePhone || isPassenger
                          ? 'Phone number'
                          : 'Email address',
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 8),

                    TextFormField(
                      controller: _usePhone
                          ? _phoneController
                          : _emailController,
                      keyboardType: _usePhone
                          ? TextInputType.phone
                          : TextInputType.emailAddress,
                      decoration: InputDecoration(
                        hintText: _usePhone
                            ? '024 100 0003 or +233...'
                            : 'you@example.com',
                        prefixIcon: Icon(
                          _usePhone
                              ? Icons.phone_outlined
                              : Icons.email_outlined,
                        ),
                        filled: true,
                        fillColor: Colors.white,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      validator: (value) {
                        if (value == null || value.trim().isEmpty) {
                          return _usePhone
                              ? 'Enter your phone number'
                              : 'Enter your email address';
                        }

                        if (!_usePhone &&
                            !RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
                                .hasMatch(value.trim())) {
                          return 'Enter a valid email address';
                        }

                        if (_usePhone &&
                            _normalisePhone(value)
                                    .replaceAll(RegExp(r'\D'), '')
                                    .length !=
                                12) {
                          return 'Enter a valid Ghana phone number';
                        }

                        return null;
                      },
                    ),

                    const SizedBox(height: 20),

                    const Text(
                      'Password',
                      style: TextStyle(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 8),

                    TextFormField(
                      controller: _passwordController,
                      obscureText: _obscurePassword,
                      decoration: InputDecoration(
                        hintText: 'Enter your password',
                        prefixIcon: const Icon(Icons.lock_outline),
                        suffixIcon: IconButton(
                          onPressed: () {
                            setState(() {
                              _obscurePassword = !_obscurePassword;
                            });
                          },
                          icon: Icon(
                            _obscurePassword
                                ? Icons.visibility_outlined
                                : Icons.visibility_off_outlined,
                          ),
                        ),
                        filled: true,
                        fillColor: Colors.white,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      validator: (value) {
                        if (value == null || value.isEmpty) {
                          return 'Enter your password';
                        }
                        return null;
                      },
                    ),

                    const SizedBox(height: 28),

                    SizedBox(
                      width: double.infinity,
                      height: 52,
                      child: FilledButton(
                        onPressed: _isLoading ? null : _login,
                        style: FilledButton.styleFrom(
                          backgroundColor: darkGreen,
                          foregroundColor: Colors.white,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                        ),
                        child: _isLoading
                            ? const SizedBox(
                                height: 22,
                                width: 22,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: Colors.white,
                                ),
                              )
                            : const Text(
                                'Sign in',
                                style: TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                      ),
                    ),

                    const SizedBox(height: 18),

                    if (isPassenger)
                      Center(
                        child: TextButton(
                          onPressed: () {
                            Navigator.push(
                              context,
                              MaterialPageRoute(
                                builder: (_) =>
                                    const PassengerRegisterScreen(),
                              ),
                            );
                          },
                          child: const Text(
                            "Don't have an account? Register",
                            style: TextStyle(
                              color: darkGreen,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _methodButton({
    required String label,
    required bool selected,
    required VoidCallback onTap,
  }) {
    return OutlinedButton(
      onPressed: onTap,
      style: OutlinedButton.styleFrom(
        backgroundColor:
            selected ? const Color(0xFFEAF3EF) : Colors.white,
        foregroundColor: darkGreen,
        side: BorderSide(
          color: selected ? darkGreen : Colors.grey.shade300,
        ),
        padding: const EdgeInsets.symmetric(vertical: 14),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
      ),
      child: Text(label),
    );
  }
}
