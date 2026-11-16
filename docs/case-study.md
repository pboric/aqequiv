# What a year of real data showed

The package was run on a full co-location study: three units of one optical
sensor system next to the gravimetric reference method (EN 12341) at an
urban background site, for one calendar year, with about 364 daily pairs
per unit for PM10 and PM2.5. The study had been evaluated earlier with
separately written code. The data belong to the institute that ran the
study and are not published; this page gives the findings only.

## The package agrees with an independent calculation

- The earlier analysis printed 24 relative expanded uncertainties (two
  fractions, three units, raw readings and three corrections). Its code,
  set to orthogonal regression, and `aqequiv` give the same 24 numbers.
- The between-unit uncertainty of all six pairs of units is identical to
  the earlier table.

## The regression method changes the answer

The earlier analysis used Deming regression with a variance ratio of 5,
which assumes the sensor's error variance is five times the reference's.
The Guide prescribes orthogonal regression, a ratio of 1.

| PM10, expanded relative uncertainty at 50 µg/m³ | Unit 1 | Unit 2 | Unit 3 |
|---|---|---|---|
| raw readings, ratio 5 | 60.4 % | 34.8 % | 50.7 % |
| raw readings, orthogonal | 75.4 % | 41.0 % | 64.7 % |
| corrected with humidity and temperature, ratio 5 | 25.2 % | 24.8 % | 28.9 % |
| corrected with humidity and temperature, orthogonal | 23.4 % | 23.1 % | 26.4 % |

The direction differs between the two cases. Raw readings had slopes above
1, and the orthogonal line is steeper still, so the bias at the limit value
grows. Corrected values come from a regression model and are pulled towards
the mean (slope below 1); the orthogonal line is closer to 1, so the bias
shrinks. A result close to the 25 % objective can therefore fall on either
side of it depending on a choice that is easy to overlook. For PM2.5 the
two methods differed by less than 0.3 percentage points after correction.

## Not equivalent, but classifiable as a sensor

Against the criteria for equivalent methods the units fail, even after
correction: the between-unit uncertainty of one pair is 3.0 µg/m³ (limit
2.5), and on the high-concentration subset the uncertainty is 44 to 66 %.

CEN/TS 17660-2 asks a different question, and gives a more useful answer:

| | PM10 | PM2.5 |
|---|---|---|
| raw readings | no class | no class |
| one linear correction for all units | Class 2 | Class 1 |

- **The intercept decided the raw result.** The raw PM10 intercepts were
  −7.7 to −9.7 µg/m³, outside the ±7 µg/m³ allowed for Class 3, although
  the uncertainty of every unit was within Class 2. A slope and intercept
  correction removed this.
- **The coarse fraction limits PM10.** The sensor's PM10-2.5 followed the
  reference with a slope of 0.49 and R² of 0.47; Class 1 needs 0.5 to 2 and
  R² above 0.5.
- **The classes are provisional.** The humidity test needs hourly data from
  an equivalent method, and the reference here was daily gravimetry. The
  specification also asks for two sites; the study had one.

## What changed in the package

- A class that depends on a test that was not supplied is now reported as
  provisional, with the missing test named.
- The markers in the Modified Target Diagram are explained in a legend; on
  real data their labels overlapped.
- A negative intercept is printed as `y + 8.574`, not `y - -8.574`.
- The tests now include a comparison with the closed form of Deming
  regression.
