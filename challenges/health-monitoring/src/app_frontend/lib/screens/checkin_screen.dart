import 'package:app_frontend/screens/status_screen.dart';
import 'package:flutter/material.dart';

import 'package:app_frontend/logic/view_models.dart';
import 'package:app_frontend/logic/models.dart';
import 'package:app_frontend/screens/login_screen.dart';
import 'package:flutter/services.dart';

class CheckinScreen extends StatefulWidget {
  const CheckinScreen({super.key});

  @override
  State<CheckinScreen> createState() => _CheckinScreenState();
}

class _CheckinScreenState extends State<CheckinScreen> {

  /// The index of our current question
  int currentQuestionIndx = 0;

  bool gettingSensorData = false;

  @override
  Widget build(BuildContext context) {
    
    final currentQuestion = AppData.instance.checkinQuestions[currentQuestionIndx];

    return Scaffold(
      resizeToAvoidBottomInset: false,
      appBar: AppBar(
        backgroundColor: Colors.lightBlue,
        title: Center(
          child: Text(
            "Quick Check-In",
            style: TextStyle(
              color: Colors.white,
              fontSize: 24,
              fontWeight: FontWeight.bold
            )
          )
        ),
      ),

      body: Stack(
        children: [
          Positioned.fill(
            child: Image.asset(
              "assets/checkin_screen.png",
              fit: BoxFit.fill,
            ),
          ),

          Positioned.fill(
            child: Center(
              child: Padding(
                padding: const EdgeInsets.all(8),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                
                    Spacer(),

                    Text(
                      currentQuestion.title,
                      style: TextStyle(fontSize: 24),
                      textAlign: TextAlign.center,
                    ),
                    SizedBox(height: 15),
                
                    // Give each input form a key
                    // If it's a number question, give a text field to get the answer
                    if (currentQuestion.type == QuestionType.num)
                      SizedBox(
                        width: 150,
                        child: NumTextField(key: ObjectKey(currentQuestion), q: currentQuestion)
                      ),
                
                    // If it's a 1-5, give a slider
                    if (currentQuestion.type == QuestionType.onetofive)
                      OneToFiveSlider(key: ObjectKey(currentQuestion), q: currentQuestion),
                
                    // If it's a yes / no, show 2 respective buttons
                    if (currentQuestion.type == QuestionType.yesno)
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                        children: [

                          // No button
                          SizedBox(
                            width: 115,
                            height: 55,
                            child: FilledButton(
                              style: FilledButton.styleFrom(backgroundColor: const Color.fromARGB(255, 255, 100, 100)),
                              onPressed: () async {
                                currentQuestion.answer = 0;
                                
                                if (currentQuestionIndx + 1 < AppData.instance.checkinQuestions.length) {
                                 
                                  setState(() {
                                    currentQuestionIndx++;
                                  });

                                } else {
                                  setState(() {
                                    gettingSensorData = true;
                                  });

                                  await AppData.instance.loadSensorData(CurrentUser.instance.crewId);

                                  setState(() {
                                    gettingSensorData = false;
                                  });

                                  if (!context.mounted) return;

                                  Navigator.pushReplacement(
                                    context,
                                    MaterialPageRoute(builder: (_) => StatusScreen())
                                  );
                                }
                              },
                            
                              child: Text("No", style: TextStyle(fontSize: 18)),
                            ),
                          ),

                          // Yes button
                          SizedBox(
                            width: 115,
                            height: 55,
                            child: FilledButton(
                              style: FilledButton.styleFrom(backgroundColor: const Color.fromARGB(255, 142, 250, 18)),
                              onPressed: () async {
                                currentQuestion.answer = 1;

                                if (currentQuestionIndx + 1 < AppData.instance.checkinQuestions.length) {
                                  
                                  setState(() {
                                    currentQuestionIndx++;
                                  });

                                } else {
                                  setState(() {
                                    gettingSensorData = true;
                                  });

                                  await AppData.instance.loadSensorData(CurrentUser.instance.crewId);
                                  
                                  setState(() {
                                    gettingSensorData = false;
                                  });

                                  if (!context.mounted) return;

                                  Navigator.pushReplacement(
                                    context,
                                    MaterialPageRoute(builder: (_) => StatusScreen())
                                  );
                                }
                              },
                            
                              child: Text("Yes", style: TextStyle(fontSize: 18, color: Colors.grey.shade800)),
                            ),
                          ),
                        ],
                      ),

                    Spacer(),

                    // If we're not on the first question, show the back button.
                    Row(
                      children: [

                        if (currentQuestionIndx > 0)
                          SizedBox(
                            width: 110,
                            height: 50,
                            child: FilledButton(
                              onPressed: () {
                                setState(() {
                                  currentQuestionIndx--;
                                });
                              },
                            
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(Icons.arrow_back),
                                  Text(" Back", style: TextStyle(fontSize: 16)),
                                ],
                              ),
                            ),
                          ),

                        Spacer(),

                        // If we're not on the last question, show the next button.
                        if (currentQuestionIndx + 1 < AppData.instance.checkinQuestions.length)
                          SizedBox(
                            width: 110,
                            height: 50,
                            child: FilledButton(

                              onPressed: () {
                                if (currentQuestion.answer != null) {
                                
                                  setState(() {
                                    currentQuestionIndx++;
                                  });

                                } else {
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    SnackBar(
                                      content: Text("Can't continue with no answer given!"),
                                      showCloseIcon: true,
                                      duration: Duration(seconds: 4),
                                      padding: EdgeInsets.all(10),
                                    )
                                  );
                                }

                              },
                            
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Text("Next ", style: TextStyle(fontSize: 16)),
                                  Icon(Icons.arrow_forward),
                                ],
                              ),
                            ),
                          ),

                        // If we are on the last question, show the submit button.
                        if (currentQuestionIndx + 1 == AppData.instance.checkinQuestions.length)
                          SizedBox(
                            width: 110,
                            height: 50,
                            child: FilledButton(

                              onPressed: () {
                                if (currentQuestion.answer != null) {
                                
                                  setState(() {
                                    currentQuestionIndx++;
                                  });

                                } else {
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    SnackBar(
                                      content: Text("Can't continue with no answer given!"),
                                      showCloseIcon: true,
                                      duration: Duration(seconds: 4),
                                      padding: EdgeInsets.all(10),
                                    )
                                  );
                                }

                              },
                            
                              child: Text("Submit"),
                            ),
                          ),
                      ],
                    ),

                  ],
                ),
              )
            ),
          ),


          // Loading (waiting for the sensor data)
          if (gettingSensorData)
            Positioned.fill(
              child: Container(
                color: const Color.fromARGB(150, 10, 0, 0),
                child: Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [

                      Text(
                        "Waiting for sensor data",
                        style: TextStyle(fontSize: 26, color: Colors.white),
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
              ),
            ),
        ],
      ),
    );

  }

}

class NumTextField extends StatefulWidget {
  const NumTextField({super.key, required this.q});

  final Question q;

  @override
  State<NumTextField> createState() => _NumTextFieldState();
}

class _NumTextFieldState extends State<NumTextField> {

  TextEditingController numController = TextEditingController();

  @override
  Widget build(BuildContext context) {
    
    return TextField(
      controller: numController,
      decoration: fieldDecoration("Answer"),
      keyboardType: TextInputType.number,
      inputFormatters: [
        FilteringTextInputFormatter.digitsOnly,
      ],

      onChanged: (value) {
        int? ans = int.tryParse(value);
        if (ans != null) {
          widget.q.answer = ans;
        }
      },
    );

  }

}

class OneToFiveSlider extends StatefulWidget {
  const OneToFiveSlider({super.key, required this.q});

  final Question q;

  @override
  State<OneToFiveSlider> createState() => _OneToFiveSliderState();
}

class _OneToFiveSliderState extends State<OneToFiveSlider> {

  int sliderValue = 3;

  @override
  void initState() {
    super.initState();

    widget.q.answer = 3;
  }

  @override
  Widget build(BuildContext context) {
    
    return Column(
      children: [

        Slider(
          label: sliderValue.toString(),
          divisions: 4,
          max: 5,
          min: 1,
          value: sliderValue.toDouble(),
          
          onChanged: (value) {
            setState(() {
              sliderValue = value.toInt();
            });
          },
        ),

        Text(
          sliderValue.toString(),
          style: TextStyle(fontSize: 20)
        )

      ],
    );

  }

}