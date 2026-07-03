within ;

model GaussianResponseGlucose
  parameter Real initialGlucose = 6.0 "Initial glucose in mmol/L";
  parameter Integer nEvents = 0 "Number of glucose-changing events";
  parameter Real eventTimes[nEvents] = fill(0.0, nEvents) "Event times in seconds";
  parameter Real eventAmplitudes[nEvents] = fill(0.0, nEvents) "Peak effects in mmol/L";
  parameter Real peakTimes[nEvents] = fill(3600.0, nEvents) "Times to peak effect in seconds";
  parameter Real durations[nEvents] = fill(10800.0, nEvents) "Effect durations in seconds";
  Real glucose "Simulated glucose in mmol/L";
  Real effects[nEvents] "Individual event effects in mmol/L";
protected
  Real sigma[nEvents];
equation
  for i in 1:nEvents loop
    sigma[i] = max(durations[i] / 6.0, 1.0);
    effects[i] = if time < eventTimes[i] or time > eventTimes[i] + durations[i] then 0 else
      eventAmplitudes[i] * exp(-0.5 * ((time - eventTimes[i] - peakTimes[i]) / sigma[i]) ^ 2);
  end for;

  glucose = max(0.0, initialGlucose + sum(effects));
end GaussianResponseGlucose;
