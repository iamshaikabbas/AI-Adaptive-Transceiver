@echo off
set "PROJDIR=C:\MY DATA ANALYTICS FILES AND PROJECTS\MAJOR\AI-Adaptive-Transceiver"
set "MATLABDIR=%PROJDIR%\OTFS MRC detection MATLAB code"
set "MATLAB_EXE=C:\MY DATA ANALYTICS FILES AND PROJECTS\Matlab\bin\matlab.exe"
cd /d "%MATLABDIR%"
"%MATLAB_EXE%" -batch "run('Results/FinalEvaluation/run_full_dataset.m')"
