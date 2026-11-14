import 'dart:ui';

import 'package:app_frontend/logic/models.dart';
import 'package:app_frontend/screens/checkin_screen.dart';
import 'package:app_frontend/screens/status_screen.dart';
import 'package:flutter/material.dart';

InputDecoration fieldDecoration(String label) => InputDecoration(
  labelText: label,
  labelStyle: TextStyle(fontSize: 14),
  isDense: true,
  filled: true,
  fillColor: Colors.grey.shade100,
  border: OutlineInputBorder(
    borderRadius: BorderRadius.circular(12),
    borderSide: BorderSide.none,
  ),
  focusedBorder: OutlineInputBorder(
    borderRadius: BorderRadius.circular(12),
    borderSide: const BorderSide(color: Colors.blue, width: 1.5),
  ),
);

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {

  TextEditingController usernameController = TextEditingController();
  TextEditingController passwordController = TextEditingController();

  bool _passwordVisible = false;

  bool loggingIn = false;

  @override
  void dispose() {
    super.dispose();
    usernameController.dispose();
    passwordController.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      resizeToAvoidBottomInset: false,
      body: Stack(
        children: [

          Positioned.fill(
            child: Image.asset(
              "assets/login_bg.jpg",
              fit: BoxFit.fill,
            )
          ),

          Positioned.fill(
            child: Padding(
              padding: EdgeInsetsGeometry.all(16),
              child: Center(

                child: ClipRRect(
                  borderRadius: BorderRadiusGeometry.circular(20),
                  child: BackdropFilter(
                    filter: ImageFilter.blur(
                      sigmaX: 3,
                      sigmaY: 3,
                    ),

                    child: Padding(
                      padding: EdgeInsetsGeometry.all(8),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                      
                          // User icon
                          Container(
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(50),
                              border: Border.all(color: Colors.black, width: 1.5),
                              color: Colors.lightBlue,
                            ),
                      
                            child: Padding(
                              padding: const EdgeInsets.all(8),
                              child: Icon(
                                Icons.person,
                                size: 60,
                                color: Colors.white,
                              ),
                            ),
                          ),
                      
                          SizedBox(height: 20),
                      
                          Text(
                            "Login to Astrokratis",
                            style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Colors.white),
                            textAlign: TextAlign.center,
                          ),
                      
                          SizedBox(height: 20),
                      
                          // Username textfield
                          TextField(
                            controller: usernameController,
                            decoration: fieldDecoration("Username"),
                          ),
                      
                          SizedBox(height: 5),
                      
                          // Password textfield
                          TextField(
                            controller: passwordController,
                            obscureText: !_passwordVisible,
                            decoration: InputDecoration(
                              labelText: "Password",
                      
                              isDense: true,
                              filled: true,
                              fillColor: Colors.grey.shade100,
                              border: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(12),
                                borderSide: BorderSide.none,
                              ),
                              focusedBorder: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(12),
                                borderSide: const BorderSide(color: Colors.blue, width: 1.5),
                              ),
                        
                              // Including an icon on the right to turn password hiding (*******) on / off
                              suffixIcon: IconButton(
                                icon: _passwordVisible ? Icon(Icons.visibility) : Icon(Icons.visibility_off),
                                onPressed: () {
                                  setState(() {
                                    _passwordVisible = !_passwordVisible;
                                  });
                                },
                              ),
                            ),
                          ),
                      
                          SizedBox(height: 30),
                      
                          // The submit button
                          SizedBox(
                            width: 120,
                            height: 60,
                            child: FilledButton(
                              onPressed: () async {
                                setState(() {
                                  loggingIn = true;
                                });

                                final success = await CurrentUser.instance.loginUser(usernameController.text, passwordController.text);

                                setState(() {
                                  loggingIn = false;
                                });

                                if (!context.mounted) return;

                                if (success) {
                                  Navigator.pushReplacement(
                                    context,
                                    MaterialPageRoute(builder: (_) => CheckinScreen())
                                  );
                                }
                              },
                            
                              child: Text(
                                "Submit",
                                style: TextStyle(fontSize: 20),
                              ),
                            ),
                          ),
                      
                        ],
                      ),
                    )
                  )
                )
              ),
            ),
          ),


          // Waiting for authentication
          if (loggingIn)
            Positioned.fill(
              child: Container(
                color: const Color.fromARGB(150, 0, 0, 0),
                child: Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [

                      Text(
                        "Waiting for authentication",
                        style: TextStyle(fontSize: 26, color: Colors.white),
                        textAlign: TextAlign.center,
                      ),

                      SizedBox(height: 15),

                      SizedBox(
                        width: 50,
                        height: 50,
                        child: CircularProgressIndicator(
                          color: Colors.white,
                          strokeWidth: 6,
                        )
                      )

                    ],
                  ),
                )
              )
            ),

        ],
      )
    );
  }

}
