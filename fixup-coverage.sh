#!/bin/bash
##
# The coverage parser expects the attributes in the coverage to be in a particular
# order. It's using a regular expression to parse the coverage output, because of
# course it is.
# https://github.com/orgoro/coverage/blob/main/src/coverage.ts#L69
#
# So we'll try to fix that up. And because we're just as good, we'll use regular
# expressions to fix a regular expression problem.
# Yay.
#

# Oh this is so awful
lines_valid=$(grep -o 'lines-valid="[0-9]*"' artifacts/coverage.xml | sed s/[^0-9]//g | head -1)
lines_covered=$(grep -o 'lines-covered="[0-9]*"' artifacts/coverage.xml | sed s/[^0-9]//g | head -1)
line_rate=$(grep -o 'line-rate="[0-9.]*"' artifacts/coverage.xml | sed s/[^0-9.]//g | head -1)

cat <<EOM
Coverage figures:
  Lines checked: $lines_valid
  Lines covered: $lines_covered
  Coverage: $line_rate
EOM


# We strip out the 3 attributes first.
# Then we add them at the beginning in the right order.
sed -E -e 's/(<coverage.*)lines-valid="[0-9]*"/\1/' \
       -e 's/(<coverage.*)lines-covered="[0-9]*"/\1/' \
       -e 's/(<coverage.*)line-rate="[0-9.]*"/\1/' \
       -e "s/<coverage /<coverage lines-valid=\"$lines_valid\" lines-covered=\"$lines_covered\" line-rate=\"$line_rate\" /" \
       artifacts/coverage.xml > artifacts/coverage-orgoro.xml
