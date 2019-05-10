import mido

#outport = mido.open_output('Synth input port (Qsynth2:0)')
#assert outport != None

inport = mido.open_input('Mobile Keys 49 MIDI 1')
assert inport != None

while True:
    mesg = inport.receive()
    print(mesg)
#    outport.send(mesg)
