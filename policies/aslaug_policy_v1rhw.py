import tensorflow as tf
from stable_baselines.common.policies import ActorCriticPolicy
from tensorflow.keras.layers import Lambda


class AslaugPolicy(ActorCriticPolicy):
    def __init__(self, sess, ob_space, ac_space, n_env, n_steps, n_batch,
                 reuse=False, **kwargs):
        super(AslaugPolicy, self).__init__(sess, ob_space, ac_space,
                                           n_env, n_steps, n_batch,
                                           reuse=reuse, scale=False)

        # Scale observation
        with tf.variable_scope("observation_scaling", reuse=reuse):
            obs_avg = tf.constant((self.ob_space.high+self.ob_space.low)/2.0,
                                  name="obs_avg")
            obs_dif = tf.constant((self.ob_space.high - self.ob_space.low),
                                  name="obs_diff")
            shifted = tf.math.subtract(self.processed_obs, obs_avg)
            proc_obs = tf.math.divide(shifted, obs_dif)

        if "obs_slicing" in kwargs and kwargs["obs_slicing"] is not None:
            obs_slicing = kwargs["obs_slicing"]
        else:
            obs_slicing = [0, 6, 9, 57, 64, 71, 272, 473]
        # Create network
        with tf.variable_scope("model/inputs", reuse=reuse):
            lrelu = tf.nn.leaky_relu
            o = obs_slicing
            in_sp = self.crop(1, o[0], o[1])(proc_obs)
            in_mb = self.crop(1, o[1], o[2])(proc_obs)
            in_lp = self.crop(1, o[2], o[3])(proc_obs)
            in_jp = self.crop(1, o[3], o[4])(proc_obs)
            in_jv = self.crop(1, o[4], o[5])(proc_obs)
            in_sc1 = self.crop(1, o[5], o[6])(proc_obs)
            in_sc2 = self.crop(1, o[6], o[7])(proc_obs)

        with tf.variable_scope("model/scan_block", reuse=reuse):
            s1_0 = tf.expand_dims(in_sc1, -1)
            s1_1 = tf.layers.Conv1D(8, 11, activation=lrelu, name="s1_1")(s1_0)
            s1_2 = tf.layers.MaxPooling1D(10, 10, name="s1_3")(s1_1)
            s1_3 = tf.layers.Conv1D(4, 5, activation=lrelu, name="s1_1")(s1_2)
            s1_4 = tf.layers.Flatten()(s1_3)
            s1_5 = tf.layers.Dense(128, activation=lrelu, name="s1_6")(s1_4)
            s1_out = tf.layers.Dense(64, activation=lrelu, name="s1_7")(s1_5)

            s2_0 = tf.expand_dims(in_sc2, -1)
            s2_1 = tf.layers.Conv1D(8, 11, activation=lrelu, name="s2_1")(s2_0)
            s2_2 = tf.layers.MaxPooling1D(10, 10, name="s2_3")(s2_1)
            s2_3 = tf.layers.Conv1D(4, 5, activation=lrelu, name="s2_1")(s2_2)
            s2_4 = tf.layers.Flatten()(s2_3)
            s2_5 = tf.layers.Dense(128, activation=lrelu, name="s2_6")(s2_4)
            s2_out = tf.layers.Dense(64, activation=lrelu, name="s2_7")(s2_5)

            sc_0 = tf.keras.layers.Concatenate(name="m_0")([s1_out, s2_out])
            sc_out = tf.layers.Dense(64, activation=lrelu, name="sc_out")(sc_0)

        with tf.variable_scope("model/attraction_block", reuse=reuse):
            at_0 = tf.keras.layers.Concatenate(name="mb_0")([in_sp, in_mb,
                                                             in_jv])
            at_1 = tf.layers.Dense(128, activation=lrelu, name="mb_s_0")(at_0)
            at_2 = tf.layers.Dense(128, activation=lrelu, name="mb_s_1")(at_1)
            at_out = tf.layers.Dense(64, activation=lrelu, name="mb_1")(at_2)

        with tf.variable_scope("model/repulsion_block", reuse=reuse):
            rp_0 = tf.keras.layers.Concatenate(name="mb_0")([in_lp, sc_out,
                                                             in_jv, in_mb])
            rp_1 = tf.layers.Dense(256, activation=lrelu, name="lp_s_0")(rp_0)
            rp_2 = tf.layers.Dense(128, activation=lrelu, name="lps_1")(rp_1)
            rp_out = tf.layers.Dense(128, activation=lrelu, name="lps_1")(rp_2)

        with tf.variable_scope("model/combination_block", reuse=reuse):
            c_0 = tf.keras.layers.Concatenate(name="m_0")([at_out, rp_out,
                                                           in_jp])
            c_1 = tf.layers.Dense(256, activation=lrelu, name="m_1")(c_0)
            c_2 = tf.layers.Dense(128, activation=lrelu, name="m_1")(c_1)
            c_out = tf.layers.Dense(64, activation=lrelu, name="m_1")(c_2)

        with tf.variable_scope("model/actor_critic_block", reuse=reuse):
            vf_latent = tf.layers.Dense(64, activation=lrelu,
                                        name="vf_latent")(c_out)
            pi_latent = tf.layers.Dense(32, activation=lrelu,
                                        name="vf_f_1")(c_out)

            value_fn = tf.layers.Dense(1, name='vf')(vf_latent)

            self._proba_distribution, self._policy, self.q_value = \
                self.pdtype.proba_distribution_from_latent(pi_latent,
                                                           vf_latent,
                                                           init_scale=1.0)

        self._value_fn = value_fn
        # self._initial_state = None
        self._setup_init()

    def step(self, obs, state=None, mask=None, deterministic=False):
        if deterministic:
            action, value, neglogp = self.sess.run([self.deterministic_action,
                                                    self.value_flat,
                                                    self.neglogp],
                                                   {self.obs_ph: obs})
        else:
            action, value, neglogp = self.sess.run([self.action,
                                                    self.value_flat,
                                                    self.neglogp],
                                                   {self.obs_ph: obs})
        return action, value, self.initial_state, neglogp

    def proba_step(self, obs, state=None, mask=None):
        return self.sess.run(self.policy_proba, {self.obs_ph: obs})

    def value(self, obs, state=None, mask=None):
        return self.sess.run(self.value_flat, {self.obs_ph: obs})

    def crop(self, dimension, start, end):
        # Crops (or slices) a Tensor on a given dimension from start to end
        def func(x):
            if dimension == 0:
                return x[start: end]
            if dimension == 1:
                return x[:, start: end]
            if dimension == 2:
                return x[:, :, start: end]
            if dimension == 3:
                return x[:, :, :, start: end]
            if dimension == 4:
                return x[:, :, :, :, start: end]
        return Lambda(func)
