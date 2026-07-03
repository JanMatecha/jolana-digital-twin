within ;

function approximateErf
  input Real x;
  output Real y;
protected
  Real signX;
  Real absX;
  Real t;
  Real tau;
algorithm
  signX := if x < 0 then -1.0 else 1.0;
  absX := abs(x);
  t := 1.0 / (1.0 + 0.5 * absX);
  tau := t * exp(
    -absX * absX - 1.26551223 + t * (
      1.00002368 + t * (
        0.37409196 + t * (
          0.09678418 + t * (
            -0.18628806 + t * (
              0.27886807 + t * (
                -1.13520398 + t * (
                  1.48851587 + t * (
                    -0.82215223 + t * 0.17087277)))))))));
  y := signX * (1.0 - tau);
end approximateErf;

model GaussianResponseGlucose
  parameter Real initialGlucose = 6.0 "Initial glucose in mmol/L";
  parameter Integer nEvents = 0 "Number of glucose-changing events";
  parameter Real eventTimes[nEvents] = fill(0.0, nEvents) "Event times in seconds";
  parameter Real eventAreas[nEvents] = fill(0.0, nEvents) "Integrated effects in mmol/L.s";
  parameter Real peakTimes[nEvents] = fill(3600.0, nEvents) "Times to peak effect in seconds";
  parameter Real durations[nEvents] = fill(10800.0, nEvents) "Effect durations in seconds";
  Real glucose "Simulated glucose in mmol/L";
  Real effects[nEvents] "Individual event effects in mmol/L";
protected
  Real sigma[nEvents];
  Real responseAreas[nEvents];
equation
  for i in 1:nEvents loop
    sigma[i] = max(durations[i] / 6.0, 1.0);
    responseAreas[i] = max(
      sigma[i] * sqrt(Modelica.Constants.pi / 2.0) * (
        approximateErf((durations[i] - peakTimes[i]) / (sqrt(2.0) * sigma[i])) -
        approximateErf((0.0 - peakTimes[i]) / (sqrt(2.0) * sigma[i]))),
      1e-9);
    effects[i] = if time < eventTimes[i] or time > eventTimes[i] + durations[i] then 0 else
      eventAreas[i] * exp(-0.5 * ((time - eventTimes[i] - peakTimes[i]) / sigma[i]) ^ 2) / responseAreas[i];
  end for;

  glucose = max(0.0, initialGlucose + sum(effects));
end GaussianResponseGlucose;
