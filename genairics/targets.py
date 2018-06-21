#!/usr/bin/env python
"""genairics target classes

Usually subclasses luigi.target.Target or luigi.LocalTarget
"""
import luigi

class LuigiStringTarget(str,luigi.target.Target):
    """
    Using this class to wrap a string, allows
    passing it between tasks through the output-input route
    """
    def exists(self):
        return bool(self)

class LuigiLocalTargetAttribute(luigi.LocalTarget):
    """LocalTargetAttribute extends luigi.LocalTarget,
    reguiring the existence of the LocalTarget and a 
    specific attribute set in that target

    Args:
        patch (str): file path passed to LocalTarget.
        attribute (str): Attribute name that needs to exist in LocalTarget file.
        attrvalue (bytes): Attrbute value. Will be encoded to bytes if str.
            Default value is b'set', just indicating that attirbute has been set.
    """
    def __init__(self,path,attribute,attrvalue=b'set',**kwargs):
        if isinstance(attrvalue, str): attrvalue = attrvalue.encode()
        super().__init__(path,**kwargs)
        self.attribute = attribute
        self.attrvalue = attrvalue

    def pathExists(self):
        """Returns the LocalTarget exists result.
        Can be useful to check prior to touching the attribute,
        as this would automatically create the file.
        """
        return super().exists()
        
    def exists(self):
        """Returns True if file path exists and file attribute
        is equal to attrvalue.
        """
        if self.pathExists():
            try:
                import xattr
                x = xattr.xattr(self.path)
                if x.has_key(self.attribute):
                    return x.get(self.attribute) == self.attrvalue
            except OSError:
                with open(self.attrfilename(),'rb') as attrfile:
                    return attrfile.read() == self.attrvalue
        # All other options return False
        return False

    def touch(self):
        """touch LocalTarget file and set extended attribute to attrvalue
        If file does not exist it will be created.
        """
        pathlib.Path(self.path).touch()
        try:
            import xattr
            x = xattr.xattr(self.path)
            x.set(self.attribute,self.attrvalue)
        except OSError:
            with open(self.attrfilename(),'wb') as attrfile:
                attrfile.write(self.attrvalue)

    def attrfilename(self):
        """If xattr is not os/fs supported,
        this function provides a filename 
        where attrvalue can be stored.

        TODO upon removing target this attrfile is not removed
        """
        return os.path.join(
            os.path.dirname(self.path),
            '.{}_{}.attr'.format(
                os.path.basename(self.path),
                self.attribute
            )
        )
