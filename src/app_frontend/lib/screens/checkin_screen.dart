import 'package:material_ui/material_ui.dart';
import 'package:flutter/services.dart';

import '../logic/models.dart';
import '../logic/view_models.dart';
import 'login_screen.dart';
import 'status_screen.dart';

class CheckinScreen extends StatefulWidget {
  const CheckinScreen({super.key});
  @override
  State<CheckinScreen> createState() => _CheckinScreenState();
}

class _CheckinScreenState extends State<CheckinScreen> {
  int currentQuestionIndx = 0;
  bool gettingSensorData = false;

  Future<void> advance() async {
    final data = AppData.instance;
    if (data.checkinQuestions[currentQuestionIndx].answer == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please enter a valid answer before continuing.'),
        ),
      );
      return;
    }
    if (currentQuestionIndx + 1 < data.checkinQuestions.length) {
      setState(() => currentQuestionIndx++);
      return;
    }
    setState(() => gettingSensorData = true);
    try {
      await data.submitCheckin();
      await data.loadSensorData(CurrentUser.instance.crewId);
      if (!mounted) return;
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const StatusScreen()),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(error.toString())));
    } finally {
      if (mounted) setState(() => gettingSensorData = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final questions = AppData.instance.checkinQuestions;
    final current = questions[currentQuestionIndx];
    return Scaffold(
      resizeToAvoidBottomInset: true,
      appBar: AppBar(
        backgroundColor: Colors.lightBlue,
        title: const Text('Quick Check-In'),
      ),
      body: Stack(
        children: [
          Positioned.fill(
            child: Image.asset('assets/checkin_screen.png', fit: BoxFit.fill),
          ),
          Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text('${currentQuestionIndx + 1} / ${questions.length}'),
                  const SizedBox(height: 16),
                  Text(
                    current.title,
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 24),
                  ),
                  const SizedBox(height: 20),
                  if (current.type == QuestionType.num)
                    SizedBox(
                      width: 180,
                      child: NumTextField(key: ObjectKey(current), q: current),
                    ),
                  if (current.type == QuestionType.num)
                    Text(
                      current.field == 'sleep_h'
                          ? 'Enter 0–24 hours.'
                          : 'Enter 0–500 percent.',
                    ),
                  if (current.type == QuestionType.onetofive)
                    OneToFiveSlider(key: ObjectKey(current), q: current),
                  if (current.type == QuestionType.symptoms)
                    SymptomsInput(key: ObjectKey(current), q: current),
                  if (current.type == QuestionType.yesno)
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        for (final answer in [0, 1])
                          Padding(
                            padding: const EdgeInsets.all(8),
                            child: ChoiceChip(
                              label: Text(answer == 1 ? 'Yes' : 'No'),
                              selected: current.answer == answer,
                              onSelected: gettingSensorData
                                  ? null
                                  : (_) =>
                                        setState(() => current.answer = answer),
                            ),
                          ),
                      ],
                    ),
                  const SizedBox(height: 24),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      if (currentQuestionIndx > 0)
                        TextButton(
                          onPressed: gettingSensorData
                              ? null
                              : () => setState(() => currentQuestionIndx--),
                          child: const Text('Back'),
                        ),
                      FilledButton(
                        onPressed: gettingSensorData ? null : advance,
                        child: Text(
                          currentQuestionIndx + 1 == questions.length
                              ? 'Submit'
                              : 'Next',
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          if (gettingSensorData)
            const Positioned.fill(
              child: ColoredBox(
                color: Color.fromARGB(150, 10, 0, 0),
                child: Center(child: CircularProgressIndicator()),
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
  late final TextEditingController numController;

  @override
  void initState() {
    super.initState();
    numController = TextEditingController(
      text: widget.q.answer?.toString() ?? '',
    );
  }

  @override
  void dispose() {
    numController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: numController,
      decoration: fieldDecoration("Answer"),
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
      inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r"[0-9.]"))],

      onChanged: (value) {
        final ans = num.tryParse(value);
        final max = widget.q.field == 'sleep_h' ? 24 : 500;
        widget.q.answer = ans != null && ans.isFinite && ans >= 0 && ans <= max
            ? ans
            : null;
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

    sliderValue = (widget.q.answer as int?) ?? 3;
    widget.q.answer = sliderValue;
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
              widget.q.answer = sliderValue;
            });
          },
        ),

        Text(sliderValue.toString(), style: TextStyle(fontSize: 20)),
      ],
    );
  }
}

class SymptomsInput extends StatefulWidget {
  const SymptomsInput({super.key, required this.q});
  final Question q;
  @override
  State<SymptomsInput> createState() => _SymptomsInputState();
}

class _SymptomsInputState extends State<SymptomsInput> {
  late Set<String> selected;
  @override
  void initState() {
    super.initState();
    selected = Set<String>.from(widget.q.answer as List<String>? ?? []);
    widget.q.answer = selected.toList();
  }

  @override
  Widget build(BuildContext context) => Column(
    children: [
      const Text('Select all that apply, or leave empty for no symptoms.'),
      Wrap(
        spacing: 8,
        children: ['sore throat', 'fatigue', 'headache', 'nausea', 'other']
            .map(
              (name) => FilterChip(
                label: Text(name),
                selected: selected.contains(name),
                onSelected: (value) {
                  setState(() {
                    if (value) {
                      selected.add(name);
                    } else {
                      selected.remove(name);
                    }
                    widget.q.answer = selected.toList()..sort();
                  });
                },
              ),
            )
            .toList(),
      ),
    ],
  );
}
