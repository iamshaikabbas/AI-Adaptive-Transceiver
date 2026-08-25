# Phase 2 - OTFS/ODDM decision-region analysis (exploratory grid)

Conditions analysed: 180 (SNR {-5,0,5,10,15,20} dB x speed {0,50,150,250,350} km/h x profiles {EPA,EVA,ETU} x {QPSK,16QAM}, paired trials).

Winner rule: lower mean BER over paired trials; relative gap <10% => tie.

## Overall

        conditions
winner            
OTFS            74
tie             71
ODDM            35

## By channel profile

winner   OTFS  ODDM  tie
profile                 
EPA        22     7   31
ETU        32    10   18
EVA        20    18   22

## By modulation

winner      OTFS  ODDM  tie
modulation                 
4              9    35   46
16            65     0   25

## By profile x modulation

winner              OTFS  ODDM  tie
profile modulation                 
EPA     4              1     7   22
        16            21     0    9
ETU     4              8    10   12
        16            24     0    6
EVA     4              0    18   12
        16            20     0   10

## By SNR band (QPSK only)

winner    OTFS  ODDM  tie
snr_band                 
<=0          0    12   18
5            0     6    9
10           2     9    4
>=15         7     8   15

## By speed band (QPSK only)

winner      OTFS  ODDM  tie
spd_band                   
static-low     2     4   12
mid            2     3   13
fast           2     8    8
very-fast      3    20   13

## Median relative BER gap (positive => OTFS better)

profile  modulation
EPA      4            -0.060519
         16            0.814554
ETU      4            -0.024118
         16            0.935895
EVA      4            -0.200789
         16            0.277259

