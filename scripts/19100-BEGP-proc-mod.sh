#!/bin/bash

pyrtkproc.py -d ~/RxTURP/BEGPIOS/BEGP/rinex/19100 -r BEGP1000-MOD.19O -f 4 -m single -c 5 -e BEGP1000-MOD.19E -g gal -t ~/amPython/pyRTKLib/rnx2rtkp.tmpl -i brdc -a saas -s brdc -l INFO DEBUG -o
