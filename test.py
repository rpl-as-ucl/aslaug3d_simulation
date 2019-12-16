import time
from envs.aslaug_v6 import AslaugEnv


N = 100000
env = AslaugEnv(gui=True)
env.reset()

ts = time.time()
for i in range(N):
    o,r,d,i = env.step(env.action_space.sample())
    if d:
        env.reset()
te = time.time()
print("Took {}s".format(te-ts))
print("Runs at {}Hz".format(N/(te-ts)))
print("Corresponds to RTF of {}".format(N/(te-ts)/50.0))
