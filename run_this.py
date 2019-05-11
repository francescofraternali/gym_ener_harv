import gym
import gym_en_harv
env = gym.make('gym_en_harv-v0')

#import gym
#env = gym.make("CartPole-v1")
observation = env.reset()
for _ in range(1000):
  env.render()
  #action = env.action_space.sample() # your agent here (this takes random actions)
  action = _
  observation, reward, done, info = env.step(action)

  if done:
    observation = env.reset()
env.close()
