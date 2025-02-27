


class TempScheduler:

    def __init__(self, tempered_loss, milestones, temperatures):
        """
        Accepts a ``TemperedLoss``, a list of milestones, and a list of
        temperatures, which should both be the same length.  The milestones are
        epoch numbers; when a given milestone is reached, the corresponding
        temperature will be applied
        """
        self.loss = tempered_loss
        self.milestones = milestones
        self.temperatures = temperatures
        self.pointer = 0
        self.cur_epoch = -1
        self.step()


    def step(self):
        self.cur_epoch += 1

        # After reaching all milestones, do nothing.
        if self.pointer == len(self.milestones):
            return

        # On reaching milestone, update temp, and point to new milestone.
        if self.milestones[self.pointer] <= self.cur_epoch:
            self.loss.temperature = self.temperatures[self.pointer]
            self.pointer += 1


class LinearLRScheduler:

    def __init__(self, optimizer, start_lr, num_epochs, end_lr=0):
        self.opt = optimizer
        self.start_lr = start_lr
        self.end_lr = end_lr
        self.num_epochs = num_epochs
        self.cur_epoch = -1
        self.step()

    def step(self):
        self.cur_epoch += 1
        if self.cur_epoch < self.num_epochs:
            fraction_left = 1 - self.cur_epoch / self.num_epochs
            cur_lr = self.end_lr+(self.start_lr-self.end_lr)*fraction_left
        else:
            cur_lr = self.end_lr
        for param_group in self.opt.param_groups:
            param_group['lr'] = cur_lr

