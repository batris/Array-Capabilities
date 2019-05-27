#import functools
from enum import Enum

class MergeException(Exception):
    pass

class AlignError(Exception):
    pass


class ViewKind(Enum):
    CONSECUTIVE = 1
    STRIDED = 2
    ROTATED = 3
    REVERSED = 4
    STRIDED_CHUNK = 5



class ConsumedWrapper:
    def __init__(self, value = False):
        self.value = value

class ArrayView:
    def __init__(self, length, parent = None, translation = None, kind = None):

        """Create an array view of a given length.

        Keyword arguments: parent -- the underlying array, if any
        translation -- the index translation array (must be
        provided if there is a parent) kind -- what the splitting
        semantics of the array view are
        """
        if parent:
            assert not translation == None, "No translation provided for new ArrayView with parent." 
            self.__length = len(translation)
            self.__data = parent            
        else:
            #self.__translation = list(range(0,length))
            self.__data = [None] * length
            self.__length = len(self.__data)

        self.__translation = translation
        self.__kind = kind
        self.__children = []

    def __add__(self, other):
        return self.merge(other)


    def __deal__(self, indexes, splits):

        """
        If indexes = [0, 1, 2, 3, ...] and splits = n, create
        [[0, n, 2n, ...], [1, n + 1, 2n + 1, ...], [2, n + 2, 2n + 2, ...], ...]
        """

        sibling_indexes = []

        for i in range(0, splits):
            sibling_indexes.append([])

        next = 0

        for i in range(0, len(indexes) ):

            (sibling_indexes[next]).append(indexes[i]) # one per sibling until the
            next += 1                                  # round is done
            if next > splits - 1:                      # if round is done start a new
                next = 0

        return sibling_indexes

    def __eq__(self, other):

        if len(self) != len(other):
            return False

        equal = True
        i = 0
        
        while equal and i < len(self): 
            if self[i] == other[i]:
                i += 1
            else:
                equal = False

        return equal


    def __getdata__(self):
        return self.__data

    def __getitem__(self, index):
        """
        Get the element at a given index.
        """
        if index < 0:
            raise IndexError
        if  self.__kind != None:
            index = self.__translate_index__(index)
        return self.__data[index]

    def __len__(self):
        """
        Return the length of the array view.
        """
        return self.__length

    def __ne__(self, other):
        return not self.__eq__(other)

    def __setitem__(self, index, value):
        """
        Set the element at a given index.
        """
        if index < 0:
            raise IndexError
        if  self.__kind != None:
            index = self.__translate_index__(index)
        self.__data[index] = value

        #overriding slicing operation???

    def __split__(self, sequence, n):
        """
        If sequence / n = k create [sequence[0:k], sequence[k:k+1], ...].
        TODO: How is the remainder m used?
        """
        k, m = divmod(len(sequence), n)
        return  (sequence[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n))

    def __str__(self):
        """
        Return the string representation of an array view.
        """
        return_string = "["
        if  self.__kind != None:
            for item in self.__translation:
                return_string += (str(self.__data[item]) + ", ")
        else:
            for item in self.__data:
                return_string += (str(item) + ", ")

        return return_string[:-2]  + "]"

    def __translate_index__(self, index):
        """
        Translate an index of the view to an index of the underlying array.
        """
        return self.__translation[index]

    def __zip__(self, other_translation):
        result = []
        self_len = len(self.__translation)
        other_len = len(other_translation)
        shortest_len = min(self_len, other_len)

        for i in range(0, shortest_len):
            result.append(self.__translation[i])
            result.append(other_translation[i])

        if self_len > shortest_len:
            result = result + self.__translation[shortest_len:]
        elif shortest_len > self_len:
            result = result + other_translation[shortest_len:]

        return result

    def __enter__(self):
        """Start of borrowing"""
        self.borrowed = True
        pass

    def __exit__(self, a, b, c):
        """End of borrowing"""
        if self.borrowed:
            self.restore()
            self.borrowed = False

    def reverse(self):

        if self.__kind == None:
            translation = list(range(0,len(self)))
        else:
            translation = self.__translation

        translation = list(reversed(translation))

        return ArrayView( len(self), self.__data, translation, ViewKind.REVERSED )

    def rotated(self, offset = 1):
        
        if self.__kind == None:
            translation = list(range(0,len(self)))
        else:
            translation = self.__translation

        translation = translation[offset:] + translation[:offset]

        return ArrayView( len(self), self.__data, translation, ViewKind.ROTATED )

    def rotate(self, offset = 1):
        
        if self.__kind == None:
            translation = list(range(0,len(self)))
        else:
            translation = self.__translation

        self.__translation = translation[offset:] + translation[:offset]
        self.__kind = ViewKind.ROTATED

    def split_at(self, pos):
        
        l1 = pos               # first part will exclude splitting point
        l2 = len(self) - (pos)
        
        if self.__translation:
            t1 = self.__translation[:l1]
            t2 = self.__translation[pos:]
        else:
            t1 = range(0, l1)
            t2 = range(pos, len(self))

        s1 = ArrayView( l1, self.__data, t1, ViewKind.CONSECUTIVE )
        s2 = ArrayView( l2, self.__data, t2, ViewKind.CONSECUTIVE )

        for s in [s1, s2]:
            self.__children.append(s)

        return [s1, s2]

    def split_by(self, splits, chunk_len):

        sibling_indexes = []

        for i in range(0, splits):
            sibling_indexes.append([])


        if self.__kind == None:
            translation = list(range(0,len(self)))
        else:
            translation = self.__translation

        i = 0
        bucket_index = 0

        while i + chunk_len <= len(translation):
            (sibling_indexes[bucket_index]) += translation[i:i+chunk_len]
            i += chunk_len
            if bucket_index < splits - 1:
                bucket_index += 1
            else:
                bucket_index = 0

        if i < len(translation):
            # if bucket_index < splits - 1:
            #     bucket_index += 1
            # else:
            #     bucket_index = 0            
            (sibling_indexes[bucket_index]) += translation[i:]



        siblings = []
            
        for i in range(0, len(sibling_indexes)):
            siblings.append(ArrayView( len(sibling_indexes[i]) ,
                                     self.__data, sibling_indexes[i],
                                     ViewKind.STRIDED_CHUNK ))
        return siblings
        
    def split(self, splits, strided = False):

        if self.__translation:
            indexes = self.__translation
        else:
            indexes = [i for i in range(0,len(self))]
        
        kind = ViewKind.CONSECUTIVE

        if strided:
            sibling_indexes = self.__deal__(indexes, splits)
            kind = ViewKind.STRIDED
        else:
            sibling_indexes = self.__split__(indexes, splits)

        siblings = []

        for index_list in sibling_indexes: 
            s = ArrayView( len(index_list), self.__data, index_list, kind )
            siblings.append(s)
            
        for s in siblings:
            self.__children.append(s)

        return siblings

    def merge(self, other, concatenate = True):
        if other.__data == self.__data:
            if concatenate:
                result = ArrayView( len(self) + len(other), self.__data, self.__translation + other.__translation, ViewKind.CONSECUTIVE )
            else:
                result = ArrayView( len(self) + len(other), self.__data, self.__zip__(other.__translation), ViewKind.STRIDED )
        else:
            raise MergeException()

        return result

    def align(self):
        result =[]
        # can we weaken this requirement?
        if len(self.__data) == len(self.__translation):
            for item in self.__translation:                
                result.append(self.__data[item])
            self.__data = result
            self.__translation = list(range(0,len(self.__data)))
            #self.__translation = None
        else:
            raise AlignError()

# ------- functions --------------------------

def __zip_many(arrs):
    
    result = []
    for i in range(0, len(arrs[0])):
        
        for arr in arrs:
            result.append(arr[i])

    return result

def reverse(arr):
    arr.reverse()

def rotate(arr, offset = 1):
    arr.rotate(offset)

def rotated(arr, offset = 1):
    return arr.rotated(offset)

def align(arr):
    arr.align()
    return arr

def fst(arr):
    return arr[0]

def lst(arr):
    return arr[-1]

def split_at(arr, pos):  # first part will exclude pos
    return arr.split_at(pos)

def split_by(arr, num, chunk_len):
    return arr.split_by(num, chunk_len)

def split(arr, num, strided):
    return arr.split(num, strided)

def merge(arrs, concatenate = True):
    check = True
    first_data = arrs[0].__getdata__()

    for arr in arrs:
        if not first_data == arr.__getdata__():
            check = False

    if not check:
        raise MergeException()
    else:    
        if concatenate:        
            result = arrs[0]
            current_number = 1 
            while current_number < len(arrs):
                result = result.merge(arrs[current_number], True)
                current_number += 1
            return result
        else:
            length = len(arrs[0])
            for arr in arrs:
                if len(arr) != length:
                    check = False
            if not check:
                raise MergeException()
            else:

                translations = []
                
                length = 0
                
                for arr in arrs:
                    translations.append(arr._ArrayView__translation)
                    length += len(arr)

                translation = __zip_many(translations)
                
                return ArrayView( length, first_data, translation, ViewKind.STRIDED )
                        
 

        


if __name__ == '__main__':

    def get_data(n):
        return random.sample(range(1, 100), n)

    a = ArrayView(16)
    for i in range(0, len(a)): 
        a[i] = i
    


    #arr1 = merge(
        
    for arr in arrs:
        print(arr)

    i = 1

    for arr in arrs:
        for pos in range(0, len(arr)):
            arr[pos] = i
        i += 1


    for arr in arrs:
        print(arr)
