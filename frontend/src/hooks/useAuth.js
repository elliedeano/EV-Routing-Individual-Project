import { useEffect, useState } from 'react';
import { onAuthStateChanged } from 'firebase/auth';

export const useAuth = (auth) => {
  const [authReady, setAuthReady] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);

  useEffect(() => {
    if (!auth) {
      setAuthReady(true);
      return undefined;
    }

    const unsubscribe = onAuthStateChanged(auth, (user) => {
      setCurrentUser(user || null);
      setAuthReady(true);
    });

    return () => unsubscribe();
  }, [auth]);

  return { authReady, currentUser };
};
