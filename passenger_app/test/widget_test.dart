
import 'package:flutter_test/flutter_test.dart';
import 'package:passenger_app/main.dart';

void main() {
  testWidgets('Passenger app launches successfully',
      (WidgetTester tester) async {
    await tester.pumpWidget(const PassengerApp());

    expect(find.text('Trip Finder'), findsOneWidget);
  });
}
