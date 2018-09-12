import hilbert as h
import numpy as np
import torch

def sim(word, context, embedder, dictionary):
    word_id = dictionary.get_id(word)
    context_id = dictionary.get_id(context)
    word_vec, context_vec = embedder.W[word_id], embedder.W[context_id]
    product = np.dot(word_vec, context_vec) 
    word_norm = np.linalg.norm(word_vec)
    context_norm =  np.linalg.norm(context_vec)
    return product / (word_norm * context_norm)


def get_embedder(
    cooc_stats,
    embedder_type, 
    **kwargs
):

    implementation = kwargs.pop('implementation', 'torch')
    device = kwargs.pop('device', 'gpu')

    if embedder_type == 'mle':
        if implementation == 'numpy':
            # kwargs has no options specific to numpy implementation of mle
            return get_MLE_embedder(cooc_stats, **kwargs)
        elif implementation == 'torch':
            # kwargs has no special options, only 'device'
            return get_MLE_embedder_torch(cooc_stats, **kwargs)

    elif embedder_type == 'w2v':
        if implementation == 'numpy':
            # kwargs can contain 'k'.
            return get_w2v_embedder(cooc_stats, **kwargs)
        elif implementation == 'torch':
            # kwargs can contain 'k'.
            return get_w2v_embedder_torch(cooc_stats, **kwargs)

    elif embedder_type == 'glove':
        if implementation == 'numpy':
            # kwargs can contain 'X_max'.
            return get_glove_embedder(cooc_stats, **kwargs)
        elif implementation == 'torch':
            # kwargs can contain 'X_max' and 'device'.
            return get_glove_embedder_torch(cooc_stats, **kwargs)

    elif embedder_type == 'swivel':
        if implementation == 'numpy':
            # kwargs can contain 'X_max'.
            return get_swivel_embedder(cooc_stats, **kwargs)
        elif implementation == 'torch':
            # kwargs can contain 'X_max' and 'device'.
            return get_swivel_embedder_torch(cooc_stats, **kwargs)


def get_swivel_embedder(cooc_stats):
    f_swivel = get_f_swivel(cooc_stats)


def get_swivel_embedder_torch(cooc_stats):
    pass



def get_glove_embedder(cooc_stats, X_max=100.0):
    M = np.log(cooc_stats.denseNxx)
    f_glove = h.f_delta.get_f_glove(cooc_stats, X_max)
    embedder = HilbertEmbedder(M, f_delta=f_glove, learning_rate=1e-6)
    return embedder

    #solver = h.solver.NesterovSolverCautious(embedder, 1e-6)
    #return solver



def get_glove_embedder_torch(cooc_stats, X_max=100.0, device='cuda'):
    M = torch.tensor(
        np.log(cooc_stats.denseNxx), dtype=torch.float32, device=device)
    f_glove_torch = h.f_delta.get_f_glove_torch(cooc_stats, X_max)
    embedder = TorchHilbertEmbedder(M, f_delta=f_glove, learning_rate=1e-6)
    return embedder

    #solver = h.solver.NesterovSolverCautious(embedder, 1e-6)
    #return solver



def get_MLE_embedder(cooc_stats):
    M = h.corpus_stats.calc_PMI(cooc_stats)
    f_MLE = h.f_delta.get_f_MLE(cooc_stats)
    embedder = HilbertEmbedder(M, f_delta=f_MLE, learning_rate=1e-6)
    return embedder

    #solver = h.solver.NesterovSolverCautious(embedder, 1e-6)
    #return solver


def get_w2v_embedder(cooc_stats, k):
    M = h.corpus_stats.calc_shifted_PMI(cooc_stats, k)
    f_w2v = h.f_delta.get_f_w2v(cooc_stats, k)
    embedder = HilbertEmbedder(M, f_delta=f_w2v, learning_rate=1e-6)
    return embedder


def get_w2v_embedder_torch(cooc_stats, k, device='cpu'):
    M = h.corpus_stats.calc_shifted_PMI(cooc_stats, k)
    f_w2v = h.f_delta.get_f_w2v_torch(cooc_stats, M, k, device=device)
    embedder = h.torch_embedder.TorchHilbertEmbedder(
        M, f_delta=f_w2v, learning_rate=1e-6, device=device)
    return embedder


def get_torch_MLE_embedder(cooc_stats):
    M = h.corpus_stats.calc_PMI(cooc_stats)
    f_MLE = h.f_delta.get_torch_f_MLE(cooc_stats, M, device='cpu')
    embedder = h.torch_embedder.TorchHilbertEmbedder(
        M, f_delta=f_MLE, learning_rate=1e-6, device='cpu')
    return embedder

    #solver = h.solver.NesterovSolverCautious(embedder, 1e-6)
    #return solver


def get_torch_MLE_embedder_optimized(cooc_stats):
    M = h.corpus_stats.calc_PMI(cooc_stats)
    f_MLE = h.f_delta.get_torch_f_MLE_optimized(cooc_stats, M, device='cpu')
    embedder = h.torch_embedder.TorchHilbertEmbedderOptimized(
        M, f_delta=f_MLE, learning_rate=1e-6, device='cpu'
    )
    return embedder

    #solver = h.solver.NesterovSolverCautious(embedder, 1e-6)
    #return solver



# TODO: enable sharding
class HilbertEmbedder(object):

    def __init__(
        self,
        M,
        f_delta,
        d=300,
        learning_rate=1e-6,
        one_sided=False,
        constrainer=None,
        pass_args={}
    ):
        self.M = M
        self.d = d
        self.f_delta = f_delta
        self.learning_rate = learning_rate
        self.one_sided = one_sided
        self.constrainer = constrainer

        self.num_covecs, self.num_vecs = self.M.shape
        self.num_pairs = self.num_covecs * self.num_vecs
        if self.one_sided and self.num_covecs != self.num_vecs:
            raise ValueError('M must be square for a one-sided embedder.')
        self.reset()
        #self.measure(**pass_args)


    def sample_sphere(self):
        sample = np.random.random(
            (self.d, self.num_vecs)) * 2 - 1
        norms = np.linalg.norm(sample, axis=1).reshape((-1,1))
        return np.divide(sample, norms, sample)


    def reset(self):
        self.V = self.sample_sphere()
        self.temp_V = np.zeros(self.V.shape)
        self.nabla_V = np.zeros(self.V.shape)
        self.update_V = np.zeros(self.V.shape)
        if self.one_sided:
            self.W = self.V.T
            self.temp_W = self.temp_V.T
            self.nabla_W = self.nabla_V.T
            self.update_W = self.update_V.T
        else:
            self.W = self.sample_sphere().T
            self.temp_W = np.zeros(self.W.shape)
            self.nabla_W = np.zeros(self.W.shape)
            self.update_W = np.zeros(self.W.shape)
        self.M_hat = np.zeros(self.M.shape)
        self.delta = np.zeros(self.M.shape)
        self.badness = None


    def calc_badness(self):
        total_absolute_error = np.sum(abs(self.delta))
        num_cells = (self.M.shape[0] * self.M.shape[1])
        self.badness = total_absolute_error / num_cells
        return self.badness


    # TODO: Test. (esp. that offsets work.)
    def get_gradient(self, offsets=None, pass_args=None):
        """ 
        Calculate and return the current gradient.  
            offsets: 
                Allowed values: None, (dV, dW)
                    where dV and dW are is a V.shape and W.shape numpy arrays
                Temporarily applies self.V += dV and self.W += dW before 
                calculating the gradient.
            pass_args:
                Allowed values: dict of keyword arguments.
                Supplies the keyword arguments to f_delta.
        """

        pass_args = pass_args or {}
        # Determine the prediction for current embeddings.  Allow an offset to
        # be specified for solvers like Nesterov Accelerated Gradient.
        if offsets is not None:
            use_W, use_V = self.temp_W, self.temp_V
            if not self.one_sided:
                dV, dW = offsets
                np.add(self.V, dV, use_V)
                np.add(self.W, dW, use_W)
            else:
                dV = offsets
                np.add(self.V, dV, use_V)
        else:
            use_W, use_V = self.W, self.V

        np.dot(use_W, use_V, self.M_hat)

        # Determine the errors.
        self.delta = self.f_delta(self.M_hat, **pass_args)

        # Determine the gradient
        np.dot(use_W.T, self.delta, self.nabla_V)
        
        if self.one_sided:
            return self.nabla_V

        np.dot(self.delta, use_V.T, self.nabla_W)
        return self.nabla_V, self.nabla_W



    def update(self, delta_V=None, delta_W=None):
        if self.one_sided and delta_W is not None:
            raise ValueError(
                "Cannot update covector embeddings (W) for a one-sided model. "
                "Update V instead."
            )
        if delta_V is not None:
            np.add(delta_V, self.V, self.V)
        if delta_W is not None:
            np.add(delta_W, self.W, self.W)
        self.apply_constraints()


    def update_self(self, pass_args=None):
        self.get_gradient(pass_args=pass_args)
        np.multiply(self.learning_rate, self.nabla_V, self.update_V)
        np.add(self.V, self.update_V, self.V)
        if not self.one_sided:
            np.multiply(self.learning_rate, self.nabla_W, self.update_W)
            np.add(self.W, self.update_W, self.W)


    def apply_constraints(self):
        if self.constrainer is not None:
            self.constrainer(self.W, self.V)


    def cycle(self, times=1, print_badness=True, pass_args=None):
        pass_args = pass_args or {}
        for i in range(times):
            self.update_self(pass_args)
            self.apply_constraints()
            if print_badness:
                print(self.calc_badness())


    def project(self, new_d):

        delta_dim = abs(self.d - new_d)
        if delta_dim == 0:
            print('warning: no change during projection.')
            return

        elif new_d < self.d:
            mass = 1.0 / new_d
            random_projector = np.random.random((delta_dim, new_d)) * mass
            downsampler = np.append(np.eye(new_d), random_projector, axis=0)
            self.W = np.dot(self.W, downsampler)
            self.V = np.dot(downsampler.T, self.V)

        else:
            old_mass = float(self.d) / new_d
            new_mass = float(delta_dim) / new_d
            covector_extension = (np.random.random((
                self.num_covecs, delta_dim)) * 2 - 1) * new_mass
            self.W = np.append(self.W * old_mass, covector_extension, axis=1)
            vector_extension = (np.random.random((
                delta_dim, self.num_vecs)) * 2 - 1) * new_mass
            self.V = np.append(self.V * old_mass, vector_extension, axis=0)



