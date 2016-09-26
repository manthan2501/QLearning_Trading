#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Implement different matching engines to handle the actions taken by each agent
in the environment

@author: ucaiado

Created on 08/19/2016
"""
import random
import logging
import zipfile
import csv
import book
import pprint
from translators import translate_trades, translate_row

# global variable
DEBUG = True

'''
Begin help functions
'''


class Foo(Exception):
    """
    Foo is raised by any class to help in debuging
    """
    pass


'''
End help functions
'''


class OrderMatching(object):
    '''
    An order matching representation that access the agents from an environment
    and handle the interation  of the individual behaviours, translating  it as
    instructions to the Order Book
    '''

    def __init__(self, env):
        '''
        Initialize a OrderMatching object. Save all parameters as attributes
        :param env: Environment object. The Market
        :param s_instrument: string. name of the instrument of book
        '''
        # save parameters as attributes
        self.env = env
        # attributes to control the qty trades by each side
        self.i_agr_ask = 0
        self.i_agr_bid = 0
        # order flow count
        self.i_ofi = 0

    def __iter__(self):
        '''
        Return the self as an iterator object. Use next() to iterate
        '''
        return self

    def next(self):
        '''
        '''
        raise NotImplementedError

    def __call__(self):
        '''
        Return the next list of messages of the simulation
        '''
        return self.next()


class BloombergMatching(OrderMatching):
    '''
    Order matching engine that use Level I data from Bloomber to reproduce the
    order book
    '''

    def __init__(self, env, s_instrument, i_num_agents, s_fname, i_idx=None):
        '''
        Initialize a OrderMatching object. Save all parameters as attributes
        :param env: Environment object. The Market
        :param s_instrument: string. name of the instrument of book
        :param i_num_agents: integer. Number of agents
        :param s_fname: string. Name of the zip file where all files are stored
        :param i_idx: integer. The index of the start file to be read
        '''
        super(BloombergMatching, self).__init__(env)
        self.s_instrument = s_instrument
        self.i_num_agents = i_num_agents
        self.s_fname = s_fname
        self.archive = zipfile.ZipFile(s_fname, 'r')
        self.l_fnames = self.archive.infolist()
        self.max_nfiles = len(self.l_fnames)
        self.idx = 0.
        self.i_nrow = 0.
        self.s_time = ''
        self.last_date = 0
        self.best_bid = (0, 0)
        self.best_ask = (0, 0)
        self.obj_best_bid = None
        self.obj_best_ask = None
        self.i_ofi = 0
        self.i_ofi_10s = 0
        self.i_qty_traded_at_bid_10s = 0
        self.i_qty_traded_at_ask_10s = 0
        self.i_qty_traded_at_bid = 0
        self.i_qty_traded_at_ask = 0
        self.mid_price_10s = 0.
        self.b_get_new_row = True
        self.f_last_bucket = 0.
        self.f_seconds_to_group = 10.
        if i_idx:
            self.idx = i_idx

    def get_trial_identification(self):
        '''
        Return the name of the files used in the actual trial
        '''
        return self.l_fnames[int(self.idx)].filename

    def reshape_row(self, idx, row, s_side=None):
        '''
        Translate a line from a file of the bloomberg level I data
        :param idx: integer.
        :param row: dict.
        :*param s_side: string. 'BID' or 'ASK'. Determine the side of the trade
        '''
        return translate_row(idx, row, self, s_side)

    def reset(self):
        '''
        Reset the order matching and all variables needed
        '''
        # make sure that dont reset twice
        if self.i_nrow != 0:
            self.i_nrow = 0
            self.idx += 1
            self.i_qty_traded_at_bid_10s = 0
            self.i_qty_traded_at_ask_10s = 0
            self.i_qty_traded_at_bid = 0
            self.i_qty_traded_at_ask = 0
            self.i_ofi_10s = 0
            self.i_ofi = 0
            self.last_date = 0
            self.best_bid = (0, 0)
            self.best_ask = (0, 0)
            self.obj_best_bid = None
            self.obj_best_ask = None
            self.mid_price_10s = 0.
            self.f_last_bucket = 0.

    def update(self, l_msg, b_print=False):
        '''
        Update the Book and all information related to it
        :param l_msg: list. messages to use to update the book
        :*param b_print: boolean. If should print the messaged generated
        '''
        if l_msg:
            # process each message generated by translator
            for msg in l_msg:
                if b_print:
                    pprint.pprint(msg)
                    print ''
                self.my_book.update(msg)
            # process the last message and use info from row
            # to compute the number of shares traded by aggressor
            if msg['order_status'] in ['Partially Filled', 'Filled']:
                if msg['agressor_indicator'] == 'Agressive':
                    # dont process this kind of order, but keep track of
                    # the quantities traded by side
                    if msg['order_side'] == 'BID':
                        self.i_qty_traded_at_ask += msg['order_qty']
                    else:
                        self.i_qty_traded_at_bid += msg['order_qty']
        # keep the best- bid and offer in a variable
        i_bid_count = self.my_book.book_bid.price_tree.count
        i_ask_count = self.my_book.book_ask.price_tree.count
        if i_bid_count > 0 and i_ask_count > 0:
            last_bid = self.best_bid
            last_ask = self.best_ask
            o_aux = self.my_book
            best_bid = o_aux.book_bid.price_tree.max_item()
            self.obj_best_bid = best_bid[1]
            best_bid = (best_bid[0], best_bid[1].i_qty)
            best_ask = o_aux.book_ask.price_tree.min_item()
            self.obj_best_ask = best_ask[1]
            best_ask = (best_ask[0], best_ask[1].i_qty)
            # account OFI
            f_en = 0.
            if last_bid != best_bid:
                if best_bid[0] >= last_bid[0]:
                    f_en += best_bid[1]
                if best_bid[0] <= last_bid[0]:
                    f_en -= last_bid[1]
            if last_ask != best_ask:
                if best_ask[0] <= last_ask[0]:
                    f_en -= best_ask[1]
                if best_ask[0] >= last_ask[0]:
                    f_en += last_ask[1]
            self.i_ofi += f_en
            self.best_bid = best_bid
            self.best_ask = best_ask
        # hold some variables from the start of 10s fold
        if self.last_date % self.f_seconds_to_group == 0 and \
           self.f_last_bucket != self.last_date:
            self.f_last_bucket = self.last_date + 1 - 1
            self.i_ofi_10s = self.i_ofi
            self.i_ofi_10s += 1 - 1
            self.i_qty_traded_at_bid_10s = self.i_qty_traded_at_bid
            self.i_qty_traded_at_bid_10s += 1 - 1  # it is ugly
            self.i_qty_traded_at_ask_10s = self.i_qty_traded_at_ask
            self.i_qty_traded_at_ask_10s += 1 - 1
            self.mid_price_10s = (self.best_bid[0] + self.best_ask[0])/2.
        # terminate
        self.i_nrow += 1

    def next(self, b_print=False):
        '''
        Return a list of messages from the agents related to the current step
        :*param b_print: boolean. If should print the messaged generated
        '''
        # if it will open a files that doesnt exist, stop
        if int(self.idx) > self.max_nfiles:
            raise StopIteration
        # if it is the first line of the file, open it and cerate a new book
        if self.i_nrow == 0:
            s_fname = self.l_fnames[int(self.idx)]
            self.fr_open = csv.DictReader(self.archive.open(s_fname))
            self.my_book = book.LimitOrderBook(self.s_instrument)
        # try to read a row of an already opened file
        try:
            # check if should get a new row form the file
            l_msg = []
            if self.b_get_new_row:
                row = self.fr_open.next()
                self.row = row
            else:
                row = self.row
                self.b_get_new_row = True
                # [debug] start PRINT BOOKS WHEN THE BID-ASK CROSSED
                # print 'corrected'
                # print self.my_book.get_n_top_prices(5)
                # print ''
                # [debug] end PRINT BOOKS WHEN THE BID-ASK CROSSED
            # check if the prices have crossed themselfs
            b_test = True
            # make sure that there are prices in the both sides
            if int(self.row['']) <= 5:
                b_test = False
            if self.my_book.book_ask.price_tree.count == 0:
                b_test = False
            if self.my_book.book_bid.price_tree.count == 0:
                b_test = False
            i_idrow = int(self.row[''])
            if self.best_bid[0] != 0 and self.best_ask[0] != 0 and b_test:
                if self.best_bid[0] >= self.best_ask[0]:
                    # set to not get a new row before correct that
                    self.b_get_new_row = False
                    row_aux = row.copy()
                    row_aux['Type'] = 'TRADE'
                    row_aux['Size'] = min(self.best_ask[1], self.best_bid[1])
                    # determine a trade to this round
                    row = row_aux.copy()
                    # reshape the row to messages to order book
                    row['Price'] = self.best_bid[0]
                    l_msg_aux = self.reshape_row(self.i_nrow, row, 'BID')
                    row['Price'] = self.best_ask[0]
                    l_msg = self.reshape_row(self.i_nrow, row, 'ASK')
                    l_msg += l_msg_aux
                    # [debug] start PRINT BOOKS WHEN THE BID-ASK CROSSED
                    # print 'id: {}, date: {}'.format(self.row[''],
                    #                                 self.row['Date'])
                    # # pprint.pprint(l_msg)
                    # print self.my_book.get_n_top_prices(5)
                    # print ''
                    # [debug] end PRINT BOOKS WHEN THE BID-ASK CROSSED
                # check if should update the primary agent
                if len(l_msg) == 0:  # just pass here if there is no trade
                    pass
            # reshape the row to messages to order book when it wasnt yet
            if len(l_msg) == 0:
                # reshape the row to messages to order book
                l_msg = self.reshape_row(self.i_nrow, row)
            # measure the time in seconds
            l_aux = row['Date'].split(' ')[1].split(':')
            i_aux = sum([int(a)*60**b for a, b in zip(l_aux, [2, 1, 0])])
            self.last_date = i_aux
            # update the book
            self.update(l_msg, b_print=b_print)
            return l_msg
        except StopIteration:
            self.i_nrow = 0
            self.idx += 1
            self.i_qty_traded_at_bid_10s = 0
            self.i_qty_traded_at_ask_10s = 0
            self.i_qty_traded_at_bid = 0
            self.i_qty_traded_at_ask = 0
            self.i_ofi_10s = 0
            self.i_ofi = 0
            self.last_date = 0
            self.best_bid = (0, 0)
            self.best_ask = (0, 0)
            self.obj_best_bid = None
            self.obj_best_ask = None
            self.mid_price_10s = 0.
            raise StopIteration
