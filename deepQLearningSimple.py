import sys
import os
import json
import gym
from gym.envs.classic_control.mountain_car import MountainCarEnv
from gym.wrappers.time_limit import TimeLimit

import numpy as np
import random
from collections import deque

from keras.models import Sequential, load_model
from keras.layers import Dense, Dropout
from keras.optimizers import Adam

def print_progress(msg):
    sys.stdout.write("\r" + msg)
    sys.stdout.flush()


def patientMountainCar():
    env = MountainCarEnv()
    return TimeLimit(env, max_episode_steps = 10000)


class neural_network_keras :

    def __init__(self, obs_dim, action_dim, learning_rate):
        
        self.obs_dim = obs_dim
        self.action_dim = action_dim
            
        # Create a 1 layer deep neural network   
        net = Sequential()
        net.add(Dense(100, input_dim = self.obs_dim, activation = "relu"))
        # net.add(Dense(32, activation = "relu"))
        # net.add(Dense(64, activation = "relu"))
        net.add(Dense(self.action_dim))
        net.compile(loss = "mean_squared_error", optimizer = Adam(lr = learning_rate))
        self.dqn = net 
        

    def get_q_values(self, state):
        """ Calculate the q-values for all actions given a sate."""
        action_values = self.dqn.predict(state.reshape(1, self.obs_dim))[0]
        return action_values
    
    
    def optimize(self, state, action_values):
        state = state.reshape(1, self.obs_dim)
        action_values = np.array(action_values).reshape(1, self.action_dim)
        self.dqn.fit(state, action_values, epochs = 1, verbose = 0)
    

    def get_weights(self):
        return self.dqn.get_weights()
    

    def set_weights(self, weights):
         self.dqn.set_weights(weights)


    def save(self, path, name):
        if not os.path.exists("data/model/{}/".format(path)):
            os.makedirs("data/model/{}/".format(path))
        
        self.dqn.save("data/model/{}/{}".format(path, name))


 #--------------------------------------------------------------------------------------------   

class replay_memory:
    
    def __init__(self, memory_size, batch_size, gamma):
        
        # Initialize the replay memory
        self.batch_size = batch_size
        self.memory_size = memory_size
        self.memory = deque(maxlen = self.memory_size)
        
        # Hyperparameter for the q-learning step
        self.gamma = gamma

        # Counter for the replay loop
        self.counter_replay = 0
    

    def add(self, state, action, next_reward, next_state, done):
        self.memory.append([state, action, next_reward, next_state, done])
        
        
    def is_full(self):
        # Boolean return if the memory is sufficient full.
        return True if len(self.memory) == self.memory_size else False


    def q_learning_and_optimize(self, target_dqn, action_dqn):
        """
        This Q-learning update based on the original paper from deepmind:
        Human-level control through deep reinforcement learning.
        The learning happens on a replay memory of the recording.
        """
        
        # Random sample with minibatch size from replay memory after the 
        # memory is sufficient full with experiences.
        if self.is_full():

            # Display first training
            self.counter_replay += 1
            print("\tReplay memory is sufficient full, start with inner trainings loop.") if self.counter_replay == 1 else None

            # Draw a mini batch from the replay memory
            minibatch = random.sample(self.memory, self.batch_size)
            
            for sample in minibatch:
                state, action, next_reward, new_state, done = sample
                target_action_values = target_dqn.get_q_values(state)

                if done:
                    # For terminal episode
                    target_action_values[action] = next_reward

                else:
                    # Learning Bellman equation by update rule
                    target_action_values[action] = next_reward + self.gamma * max(target_dqn.get_q_values(new_state))

                # Perform a gradient descent step with respect to the action dqn parameter
                action_dqn.optimize(state, target_action_values)
                
        
        return target_dqn, action_dqn

#-------------------------------------------------------------------------------------------------------------------

class writer:

    def __init__(self):

        # Init history
        self.history = {}
        self.history["episode"] = []
        self.history["steps"] = []
        self.history["reward"] = []
        self.history["cum_win"] = []
        self.history["mean_q_values"] = []
        self.history["position"] = {}
        self.history["position"]["max_position"] = []
        self.history["position"]["final_position"] = []
    

    def add_to_history(self, episode, steps, reward, cum_win, mean_q_values, max_position, final_position):
        self.history["episode"].append(int(episode))
        self.history["steps"].append(int(steps))
        self.history["reward"].append(int(reward))
        self.history["cum_win"].append(int(cum_win))
        self.history["mean_q_values"].append(float(mean_q_values))
        self.history["position"]["max_position"].append(float(max_position))
        self.history["position"]["final_position"].append(float(final_position))
        
        
    def save(self, name):
        
        # Create a directory
        if not os.path.exists("data/history/{}".format(name)):
            os.makedirs("data/history/{}".format(name))
        
        # Convert into JSON
        y = json.dumps(self.history)
        
        # Write to local
        f = open("./data/history/{}/history.json".format(name), "w+")
        f.write(y)
        f.close()

  #-----------------------------------------------------------------------------------------------------------

class agent:
    """
    Implementation for playing the game and initialize the function 
    approxiamtion and also store the results for experience replay 
    """
    def __init__(self, env, training, render = False):

        # The game environment the agent plays
        self.env = env
        
        # Display game
        self.render = render
        
        # The action dimention
        self.action_dim = self.env.action_space.n
        
        # The observation dimention the agent observes
        self.obs_dim = self.env.observation_space.shape[0]

        # Whether we are training (True) or testing (False)
        self.training = training
        
        # Create the neural network for estimating the q values for choose action 
        self.action_dqn = neural_network_keras(obs_dim = self.obs_dim, action_dim = self.action_dim, learning_rate = 0.005)
        
        # Create a neural network as target network for the learning phase
        self.target_dqn = neural_network_keras(obs_dim = self.obs_dim, action_dim = self.action_dim, learning_rate = 0.005)
        
        # History/ storage for the results per episode
        self.writer_history = writer()

        if self.training:
            # Create replay memory only if the agent trains
            self.replay_memory = replay_memory(memory_size = 2000, 
                                               batch_size = 32, 
                                               gamma = 0.99)

            # Initialize epsilon for training
            self.epsilon = 1.0

            # Stepsize for updating the target network parameter
            self.C = 100
            
        else: 
            self.replay_memory = None
            self.C = None
        

    # Select action on a epsilon greedy algorithm.
    # During testing, epsilon is fix to avoit overfitting
    # During training, the epsilon decreases linear.
    def _epsilon_greedy(self, state):

        if self.training:
            epsilon_min = 0.1
            epsilon_decay = 0.99
            epsilon = self.epsilon * epsilon_decay
            self.epsilon = max(epsilon_min, epsilon)
        
        else:
            self.epsilon = 0.05

        action_values = self.action_dqn.get_q_values(state)

        if np.random.random() < self.epsilon:
            # Select a random action
            action = np.random.randint(low = 0, high = self.action_dim)

        else :
            # Otherwise select action with highest q value
            action = np.argmax(action_values)

        return action, action_values, self.epsilon

    # Run the game 
    def run(self, num_episode, num_steps, try_name = ""):

        # Initial the run
        counter_episodes = 0
        counter_wins = 0 
        
        while counter_episodes < num_episode:

            # Init new game after the end of an episode
            counter_episodes += 1 # Count +1 episode
            targetUpdateStep = self.C # Keep track of the target value updates
            state = self.env.reset() # Reste game-environment
            reward_episode = 0.0 # Rest episodic reward 
            action_value_episode = [] # Reset q-values
            counter_steps = 0 # Rest step counter
            max_position = 0.0 # Reset teh max position per episode
                
            for step in range(num_steps): 
                counter_steps += 1 

                # Display the game 
                if self.render:
                    self.env.render()

                # Determine the action for each step by an epsilon greedy algorithm.
                action, action_values, epsilon = self._epsilon_greedy(state)
                
                # Add optimal action value to list
                action_value_episode.append(max(action_values))

                # Execute the action in the game environment and receive
                # the next state, reward and the episode status.
                next_state, next_reward, done, _ = self.env.step(action)

                # Modify reward
                next_reward = next_state[0] 
                
                # (Re-)define the goal
                if next_state[0] >= 0.5:
                    counter_wins += 1 
                    done = True
                    next_reward = 10
                    # Store the model if the car successfully completed the taks
                    if self.training:
                        self.action_dqn.save(try_name , "success_model_episode_{}.h5".format(counter_episodes)) 

                # Sum the reward for this episode
                reward_episode += next_reward

                # Keep track of the max reached position
                max_position = max(max_position, next_state[0])

                # End of an episode when max number of steps
                if counter_steps == num_steps:
                    done = True

                # Start replay memory loop
                if self.training:
                    
                    # Add experience to the replay memory
                    self.replay_memory.add(state, action, next_reward, next_state, done)

                    # Random sample a minibatch form the experience memory, 
                    # update q values with Dynamic Programming and apply a gradient descent step
                    # per sample from the minibatch
                    self.target_dqn, self.action_dqn = self.replay_memory \
                        .q_learning_and_optimize(target_dqn = self.target_dqn, action_dqn = self.action_dqn)

                    # Update target network parameter after C steps
                    if counter_steps == targetUpdateStep:
                        weights_action = self.action_dqn.get_weights()
                        self.target_dqn.set_weights(weights_action)
                        targetUpdateStep += self.C # next update in C steps
                        print("\t Update target DQN after %s steps" % counter_steps)

                # Set state as next state
                state = next_state 

                if done:
                    break
            
            # Mean q value per episode
            mean_action_value_episode = np.mean(action_value_episode)

            # After each game/episode add the success to the over all list
            # and store the result locally
            self.writer_history.add_to_history(
                episode = counter_episodes, 
                steps = counter_steps, 
                reward = reward_episode, 
                cum_win = counter_wins, 
                mean_q_values = mean_action_value_episode, 
                max_position = max_position, 
                final_position = state[0]
                )
                
            # Store progressive in trainings mode
            if self.training:
                self.writer_history.save(try_name)
            
             # Print results
            print(" Game :: {} Wins :: {} Steps :: {} Reward {:4f} Mean Q Value :: {:4f} Max position {:4f} ".format(counter_episodes, counter_wins, counter_steps, reward_episode, mean_action_value_episode, max_position) )


#------------------------------------------------------------------------------------------------------------------------------------------

if __name__ == '__main__':
    try: 
        env.close()
    except:
        pass
    
    try_name = "version_simple_v1"

    print("Init game-environment and agent:: %s" % try_name)
    env = patientMountainCar()
    agentDQN = agent(env  = env, training = True, render = False)

    # Training
    print("Start Training")
    agentDQN.run(num_episode = 1000, num_steps = 500, try_name = try_name)

    # Saving last model
    print("Save end-of-run model")
    agentDQN.action_dqn.save(try_name, "end_of_run_model.h5") 

    print("DONE")
