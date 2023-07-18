#! /bin/bash
scp -r input_waves $1 2023asathees@infosphere.csl.tjhsst.edu:~/DenoiserModel/in
scp filenames.txt 2023asathees@infosphere.csl.tjhsst.edu:~/DenoiserModel
filename="${1%.*}"
extension="${1##*.}"
new_filename="${filename}_generated.%{extension}"
printf "Generating new string: $new_filename"
ssh -t 2023asathees@infosphere.csl.tjhsst.edu "cd ~/DenoiserModel; python run.py"
scp -r 2023asathees@infosphere.csl.tjhsst.edu:~/DenoiserModel/out/$new_filename output_files/