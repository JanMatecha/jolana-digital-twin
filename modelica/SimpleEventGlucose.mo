within ;

model SimpleEventGlucose
  parameter Real initialGlucose = 6.0 "Initial glucose in mmol/L";
  parameter Integer nEvents = 0 "Number of glucose-changing events";
  parameter Real eventTimes[nEvents] = fill(0.0, nEvents) "Event times in seconds";
  parameter Real eventEffects[nEvents] = fill(0.0, nEvents) "Glucose step changes in mmol/L";
  Real glucose(start = initialGlucose, fixed = true) "Simulated glucose in mmol/L";
equation
  der(glucose) = 0;

  for i in 1:nEvents loop
    when time >= eventTimes[i] then
      reinit(glucose, pre(glucose) + eventEffects[i]);
    end when;
  end for;
end SimpleEventGlucose;
